import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.service import patient_names
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import BranchNotFoundError
from app.modules.scheduling.statuses import AppointmentStatus as Status
from app.modules.scheduling.triage import latest_triage, urgency_rank
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
    position: int | None  # place in today's waiting line; None while in consultation
    scheduled_at: datetime
    checked_in_at: datetime | None
    consult_started_at: datetime | None
    # A visit from an earlier Lagos day that was never finished or cancelled.
    # It is shown apart, never silently hidden, so front desk can tidy it up.
    from_earlier_day: bool
    # The triage that counts (None until someone triages). Danger signs are clinical:
    # the router leaves them out for staff who may not read the clinical record.
    triage_level: str | None = None
    red_flags: tuple[str, ...] = ()


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


def _queue_entry(
    row: Appointment,
    position: int | None,
    names: dict,
    triage: dict,
    *,
    earlier: bool = False,
) -> QueueEntry:
    latest = triage.get(row.id)
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
        from_earlier_day=earlier,
        triage_level=latest.level if latest else None,
        red_flags=tuple(latest.red_flags) if latest else (),
    )


def lagos_day(moment: datetime) -> date:
    """The Lagos calendar day a moment falls on."""
    return moment.astimezone(CLINIC_TIME).date()


def _require_branch(session: Session, tenant_id: uuid.UUID, branch_id: uuid.UUID) -> None:
    if get_branch(session, tenant_id=tenant_id, branch_id=branch_id) is None:
        raise BranchNotFoundError("Branch not found.")


def get_queue(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    now: datetime | None = None,
) -> list[QueueEntry]:
    """Who is being seen and who is waiting at this branch. Looking is noted in the diary.

    Today's visits come first and only they get places in the line. Visits left open
    from earlier days come last, marked from_earlier_day, so they can be tidied up.
    """
    today = lagos_day(now or datetime.now(UTC))
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
    triage = latest_triage(session, tenant_id=tenant_id, visits=list(rows))

    current = [row for row in rows if lagos_day(row.starts_at) >= today]
    leftover = sorted(
        (row for row in rows if lagos_day(row.starts_at) < today),
        key=lambda row: (row.starts_at, str(row.id)),
    )
    in_consult = sorted(
        (row for row in current if row.status == Status.IN_CONSULT.value),
        key=lambda row: (row.consult_started_at or row.starts_at, str(row.id)),
    )
    waiting = sorted(
        (row for row in current if row.status == Status.WAITING.value),
        # Emergencies first, then urgent, then everyone else in arrival order.
        key=lambda row: (
            urgency_rank(triage.get(row.id)),
            row.checked_in_at or row.starts_at,
            str(row.id),
        ),
    )

    entries = [_queue_entry(row, None, names, triage) for row in in_consult]
    entries += [
        _queue_entry(row, place, names, triage) for place, row in enumerate(waiting, start=1)
    ]
    entries += [_queue_entry(row, None, names, triage, earlier=True) for row in leftover]
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
