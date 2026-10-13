import uuid
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_clinician
from app.modules.patients.service import PatientNotFoundError, patient_exists
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import (
    ACTIVE_STATUSES,
    AppointmentKind,
    AppointmentStatus,
    VisitType,
)
from app.modules.tenancy.service import get_branch

MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 240
DEFAULT_DURATION_MINUTES = 30
MAX_DAYS_AHEAD = 365


class InvalidAppointmentError(ValueError):
    """The appointment details are not acceptable."""


class BranchNotFoundError(Exception):
    """No branch with this ID in this clinic."""


class ClinicianNotFoundError(Exception):
    """No active doctor or nurse with this ID in this clinic."""


class SlotTakenError(Exception):
    """The clinician already has an appointment that overlaps this time."""

def clean_start_time(starts_at: datetime, now: datetime) -> datetime:
    """Check a requested start time and return it in UTC."""
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise InvalidAppointmentError("The start time must include a time zone.")
    start_utc = starts_at.astimezone(UTC)
    if start_utc < now:
        raise InvalidAppointmentError("An appointment cannot be booked in the past.")
    if start_utc > now + timedelta(days=MAX_DAYS_AHEAD):
        raise InvalidAppointmentError("An appointment cannot be booked more than a year ahead.")
    return start_utc

def _check_duration(minutes: int) -> None:
    if not MIN_DURATION_MINUTES <= minutes <= MAX_DURATION_MINUTES:
        raise InvalidAppointmentError(
            f"Duration must be between {MIN_DURATION_MINUTES} and {MAX_DURATION_MINUTES} minutes."
        )


def _check_references(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    patient_id: uuid.UUID,
    branch_id: uuid.UUID,
    clinician_id: uuid.UUID | None,
) -> None:
    """Everything an appointment points at must belong to this clinic."""
    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise PatientNotFoundError("Patient not found.")
    if get_branch(session, tenant_id=tenant_id, branch_id=branch_id) is None:
        raise BranchNotFoundError("Branch not found.")
    if clinician_id is not None and not is_active_clinician(
        session, tenant_id=tenant_id, staff_id=clinician_id
    ):
        raise ClinicianNotFoundError("Clinician not found.")


def _slot_is_taken(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    clinician_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    ignore_id: uuid.UUID | None = None,
) -> bool:
    """Does an unfinished appointment of this clinician overlap [starts_at, ends_at)?"""
    unfinished = [status.value for status in ACTIVE_STATUSES]
    statement = (
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.clinician_id) == clinician_id)
        .where(col(Appointment.status).in_(unfinished))
        .where(col(Appointment.starts_at) < ends_at)
        .where(col(Appointment.ends_at) > starts_at)
    )
    if ignore_id is not None:
        statement = statement.where(col(Appointment.id) != ignore_id)
    return session.exec(statement.limit(1)).first() is not None

def book_appointment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    branch_id: uuid.UUID,
    clinician_id: uuid.UUID,
    starts_at: datetime,
    duration_minutes: int = DEFAULT_DURATION_MINUTES,
    visit_type: str = VisitType.IN_PERSON.value,
    now: datetime | None = None,
) -> Appointment:
    """Book a visit ahead of time. The appointment and its diary line are saved together."""
    current = now or datetime.now(UTC)

    starts_at = clean_start_time(starts_at, current)
    _check_duration(duration_minutes)
    try:
        visit_value = VisitType(visit_type).value
    except ValueError:
        raise InvalidAppointmentError("Visit type must be in_person or teleconsult.") from None

    _check_references(
        session,
        tenant_id=tenant_id,
        patient_id=patient_id,
        branch_id=branch_id,
        clinician_id=clinician_id,
    )

    ends_at = starts_at + timedelta(minutes=duration_minutes)
    if _slot_is_taken(
        session,
        tenant_id=tenant_id,
        clinician_id=clinician_id,
        starts_at=starts_at,
        ends_at=ends_at,
    ):
        raise SlotTakenError("That clinician already has an appointment at that time.")

    appointment = Appointment(
        tenant_id=tenant_id,
        branch_id=branch_id,
        patient_id=patient_id,
        clinician_id=clinician_id,
        kind=AppointmentKind.SCHEDULED.value,
        visit_type=visit_value,
        status=AppointmentStatus.BOOKED.value,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by_id=actor_id,
    )
    session.add(appointment)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.APPOINTMENT_CREATE,
        patient_id=patient_id,
    )
    session.commit()
    session.refresh(appointment)
    return appointment


def register_walk_in(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    branch_id: uuid.UUID,
    clinician_id: uuid.UUID | None = None,
    duration_minutes: int = DEFAULT_DURATION_MINUTES,
    now: datetime | None = None,
) -> Appointment:
    """A patient who arrives without a booking joins the queue as `waiting`."""
    current = now or datetime.now(UTC)
    _check_duration(duration_minutes)
    _check_references(
        session,
        tenant_id=tenant_id,
        patient_id=patient_id,
        branch_id=branch_id,
        clinician_id=clinician_id,
    )

    appointment = Appointment(
        tenant_id=tenant_id,
        branch_id=branch_id,
        patient_id=patient_id,
        clinician_id=clinician_id,
        kind=AppointmentKind.WALK_IN.value,
        visit_type=VisitType.IN_PERSON.value,
        status=AppointmentStatus.WAITING.value,
        starts_at=current,
        ends_at=current + timedelta(minutes=duration_minutes),
        checked_in_at=current,
        created_by_id=actor_id,
    )
    session.add(appointment)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.APPOINTMENT_CREATE,
        patient_id=patient_id,
    )
    session.commit()
    session.refresh(appointment)
    return appointment