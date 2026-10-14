import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.service import patient_names
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import BranchNotFoundError
from app.modules.scheduling.statuses import AppointmentStatus as Status
from app.modules.tenancy.service import get_branch

# Nigeria is on West Africa Time all year (no daylight saving), so a fixed offset is exact.
# "Today" on the clinic's screens means the Lagos calendar day, not the UTC one.
CLINIC_TIME = timezone(timedelta(hours=1), "WAT")

# Shown when a name cannot be found, so a gap is visible instead of silently blank.
UNKNOWN_NAME = "(name not found)"


@dataclass(frozen=True)
class QueueEntry:
    """One line on the board: who, and where they are in the line. Name only, no other details."""

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    position: int | None  # place in the waiting line; None while in consultation
    scheduled_at: datetime
    checked_in_at: datetime | None
    consult_started_at: datetime | None


@dataclass(frozen=True)
class DayEntry:
    """One visit on a branch's day list, in any status. Name only, no other details."""

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    starts_at: datetime
    ends_at: datetime
    checked_in_at: datetime | None


def _names_for(session: Session, tenant_id: uuid.UUID, rows) -> dict[uuid.UUID, str]:
    return patient_names(
        session, tenant_id=tenant_id, patient_ids=list({row.patient_id for row in rows})
    )


def _queue_entry(row: Appointment, position: int | None, names: dict) -> QueueEntry:
    return QueueEntry(
        appointment_id=row.id,
        patient_id=row.patient_id,
        patient_name=names.get(row.patient_id, UNKNOWN_NAME),
        clinician_id=row.clinician_id,
        kind=row.kind,
        visit_type=row.visit_type,
        status=row.status,
        position=position,
        scheduled_at=row.starts_at,
        checked_in_at=row.checked_in_at,
        consult_started_at=row.consult_started_at,
    )


def _require_branch(session: Session, tenant_id: uuid.UUID, branch_id: uuid.UUID) -> None:
    if get_branch(session, tenant_id=tenant_id, branch_id=branch_id) is None:
        raise BranchNotFoundError("Branch not found.")


def get_queue(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> list[QueueEntry]:
    """Who is being seen and who is waiting at this branch. Looking is noted in the diary."""
    _require_branch(session, tenant_id, branch_id)

    # One diary line per look. It records THAT the board was viewed, not each patient on it.
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.QUEUE_VIEW,
        purpose="queue",
    )
    session.commit()

    live = [Status.WAITING.value, Status.IN_CONSULT.value]
    statement = (
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.branch_id) == branch_id)
        .where(col(Appointment.status).in_(live))
    )
    rows = session.exec(statement).all()
    names = _names_for(session, tenant_id, rows)

    in_consult = sorted(
        (row for row in rows if row.status == Status.IN_CONSULT.value),
        key=lambda row: (row.consult_started_at or row.starts_at, str(row.id)),
    )
    waiting = sorted(
        (row for row in rows if row.status == Status.WAITING.value),
        key=lambda row: (row.checked_in_at or row.starts_at, str(row.id)),
    )

    entries = [_queue_entry(row, None, names) for row in in_consult]
    entries += [_queue_entry(row, place, names) for place, row in enumerate(waiting, start=1)]
    return entries


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Midnight to midnight in Lagos, as moments the database can compare."""
    start = datetime.combine(day, time.min, tzinfo=CLINIC_TIME)
    return start, start + timedelta(days=1)


def get_day_list(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    day: date,
) -> list[DayEntry]:
    """Every visit at this branch on one Lagos day, earliest first. Looking is logged."""
    _require_branch(session, tenant_id, branch_id)

    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.APPOINTMENT_LIST,
        purpose="day_list",
    )
    session.commit()

    start, end = day_bounds(day)
    statement = (
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.branch_id) == branch_id)
        .where(col(Appointment.starts_at) >= start)
        .where(col(Appointment.starts_at) < end)
        .order_by(col(Appointment.starts_at), col(Appointment.id))
    )
    rows = session.exec(statement).all()
    names = _names_for(session, tenant_id, rows)
    return [
        DayEntry(
            appointment_id=row.id,
            patient_id=row.patient_id,
            patient_name=names.get(row.patient_id, UNKNOWN_NAME),
            clinician_id=row.clinician_id,
            kind=row.kind,
            visit_type=row.visit_type,
            status=row.status,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            checked_in_at=row.checked_in_at,
        )
        for row in rows
    ]
