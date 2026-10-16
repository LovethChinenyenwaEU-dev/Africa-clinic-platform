import uuid
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_clinician
from app.modules.notifications.service import cancel_reminders, reschedule_reminders
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import (
    ClinicianNotFoundError,
    SlotTakenError,
    _check_duration,
    _slot_is_taken,
    clean_start_time,
)
from app.modules.scheduling.statuses import AppointmentStatus as Status
from app.modules.scheduling.transitions import InvalidMoveError, check_move
from app.modules.telehealth.readiness import require_safe_teleconsult


class AppointmentNotFoundError(Exception):
    """No appointment with this ID in this clinic."""


class ClinicianMismatchError(Exception):
    """This visit belongs to a different clinician."""


def _load_locked(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    """Find one appointment of this clinic and lock it while we change it."""
    statement = (
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.id) == appointment_id)
        .with_for_update()
    )
    appointment = session.exec(statement).first()
    if appointment is None:
        raise AppointmentNotFoundError("Appointment not found.")
    return appointment


def _save(
    session: Session, appointment: Appointment, *, actor_id: uuid.UUID, action: AuditAction
) -> Appointment:
    """Save the change and its diary line together, or neither."""
    add_audit_event(
        session,
        tenant_id=appointment.tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=appointment.patient_id,
    )
    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment


def check_in(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    now: datetime | None = None,
) -> Appointment:
    """The patient has arrived and is now waiting."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    new_status = check_move(
        appointment.status, Status.WAITING.value, starts_at=appointment.starts_at, now=current
    )
    require_safe_teleconsult(session, appointment)

    appointment.status = new_status.value
    appointment.checked_in_at = current
    return _save(session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_CHECK_IN)


def start_consultation(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    now: datetime | None = None,
) -> Appointment:
    """A clinician starts seeing the patient. Whoever starts it becomes the clinician."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    new_status = check_move(
        appointment.status, Status.IN_CONSULT.value, starts_at=appointment.starts_at, now=current
    )
    if not is_active_clinician(session, tenant_id=tenant_id, staff_id=actor_id):
        raise ClinicianNotFoundError("Only an active doctor or nurse can run a consultation.")
    if appointment.clinician_id not in (None, actor_id):
        raise ClinicianMismatchError("This visit belongs to another clinician.")
    require_safe_teleconsult(session, appointment)

    appointment.clinician_id = actor_id
    appointment.status = new_status.value
    appointment.consult_started_at = current
    return _save(session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_START)


def complete_consultation(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    now: datetime | None = None,
) -> Appointment:
    """The consultation is over. Only the clinician who started it can finish it."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    new_status = check_move(
        appointment.status, Status.DONE.value, starts_at=appointment.starts_at, now=current
    )
    if appointment.clinician_id != actor_id:
        raise ClinicianMismatchError("Only the clinician who started the visit can finish it.")

    appointment.status = new_status.value
    appointment.completed_at = current
    return _save(session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_COMPLETE)


def cancel_appointment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    now: datetime | None = None,
) -> Appointment:
    """Cancel a visit that has not started. Its time becomes free again."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    new_status = check_move(
        appointment.status, Status.CANCELLED.value, starts_at=appointment.starts_at, now=current
    )

    appointment.status = new_status.value
    cancel_reminders(session, tenant_id=tenant_id, appointment_id=appointment.id)
    return _save(session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_CANCEL)


def mark_no_show(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    now: datetime | None = None,
) -> Appointment:
    """The patient never came. Only allowed once the start time has passed."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    new_status = check_move(
        appointment.status, Status.NO_SHOW.value, starts_at=appointment.starts_at, now=current
    )

    appointment.status = new_status.value
    return _save(session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_NO_SHOW)


def reschedule_appointment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    starts_at: datetime,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> Appointment:
    """Move a booked visit to a new time. It keeps its length unless a new one is given."""
    current = now or datetime.now(UTC)
    appointment = _load_locked(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if appointment.status != Status.BOOKED.value:
        raise InvalidMoveError("Only a booked appointment can be rescheduled.")

    new_start = clean_start_time(starts_at, current)
    if duration_minutes is None:
        duration_minutes = int((appointment.ends_at - appointment.starts_at).total_seconds() // 60)
    _check_duration(duration_minutes)
    new_end = new_start + timedelta(minutes=duration_minutes)

    if appointment.clinician_id is not None and _slot_is_taken(
        session,
        tenant_id=tenant_id,
        clinician_id=appointment.clinician_id,
        starts_at=new_start,
        ends_at=new_end,
        ignore_id=appointment.id,
    ):
        raise SlotTakenError("That clinician already has an appointment at that time.")

    appointment.starts_at = new_start
    appointment.ends_at = new_end
    reschedule_reminders(
        session,
        tenant_id=tenant_id,
        appointment_id=appointment.id,
        starts_at=new_start,
        now=current,
    )
    return _save(
        session, appointment, actor_id=actor_id, action=AuditAction.APPOINTMENT_RESCHEDULE
    )