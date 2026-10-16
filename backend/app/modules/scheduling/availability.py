"""Clinician availability and free slots (FR-C1).

A clinician publishes their own weekly hours: a weekday, a Lagos start and end
time, in person or remote (teleconsult), and the slot length. Free slots are those
hours cut into slots, minus anything already booked for that clinician, minus the past.

Staff may still book outside these hours (a clinic sometimes needs to); patients
booking themselves (Week 9 Step 8) may only take a free slot (is_free_slot).
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_clinician
from app.modules.scheduling.board import CLINIC_TIME
from app.modules.scheduling.models import Appointment, Availability
from app.modules.scheduling.service import BranchNotFoundError
from app.modules.scheduling.statuses import ACTIVE_STATUSES, VisitType
from app.modules.tenancy.service import get_branch

SLOT_CHOICES = (10, 15, 20, 30, 45, 60)
MAX_DAYS_SHOWN = 14


class InvalidAvailabilityError(ValueError):
    """The hours are not acceptable (end before start, unknown type, odd slot length)."""


class AvailabilityOverlapError(Exception):
    """These hours overlap hours the clinician already published for that day."""


class AvailabilityNotFoundError(Exception):
    """No such hours for this clinician in this clinic."""


class NotAClinicianForHoursError(Exception):
    """Only an active doctor or nurse publishes hours, and only their own."""


@dataclass(frozen=True)
class Slot:
    starts_at: datetime  # UTC
    ends_at: datetime
    branch_id: uuid.UUID
    visit_type: str


def _visit_type(value: str) -> str:
    try:
        return VisitType(value).value
    except ValueError:
        raise InvalidAvailabilityError("Type must be in_person or teleconsult.") from None


def add_availability(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    weekday: int,
    starts: time,
    ends: time,
    visit_type: str,
    slot_minutes: int,
    availability_id: uuid.UUID | None = None,
) -> Availability:
    """Publish weekly hours for the person adding them."""
    if not is_active_clinician(session, tenant_id=tenant_id, staff_id=actor_id):
        raise NotAClinicianForHoursError("Only an active doctor or nurse can publish hours.")
    if availability_id is not None:
        existing = get_in_tenant(session, Availability, tenant_id=tenant_id, row_id=availability_id)
        if isinstance(existing, Availability):
            return existing
    if not 0 <= weekday <= 6:
        raise InvalidAvailabilityError("Weekday must be 0 (Monday) to 6 (Sunday).")
    if starts.tzinfo is not None or ends.tzinfo is not None:
        raise InvalidAvailabilityError("Give plain Lagos times, without a time zone.")
    if starts >= ends:
        raise InvalidAvailabilityError("The end time must be after the start time.")
    if slot_minutes not in SLOT_CHOICES:
        choices = ", ".join(str(minutes) for minutes in SLOT_CHOICES)
        raise InvalidAvailabilityError(f"Slot length must be one of: {choices} minutes.")
    kind = _visit_type(visit_type)
    if get_branch(session, tenant_id=tenant_id, branch_id=branch_id) is None:
        raise BranchNotFoundError("Branch not found.")

    same_day = session.exec(
        tenant_select(Availability, tenant_id)
        .where(col(Availability.clinician_id) == actor_id)
        .where(col(Availability.weekday) == weekday)
    ).all()
    if any(starts < other.ends and other.starts < ends for other in same_day):
        raise AvailabilityOverlapError("These hours overlap hours you already published.")

    row = Availability(
        id=availability_id or uuid.uuid4(),
        tenant_id=tenant_id,
        clinician_id=actor_id,
        branch_id=branch_id,
        weekday=weekday,
        starts=starts,
        ends=ends,
        visit_type=kind,
        slot_minutes=slot_minutes,
        created_by_id=actor_id,
    )
    session.add(row)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.AVAILABILITY_ADD,
        entity_id=row.id,
    )
    session.commit()
    session.refresh(row)
    return row


def remove_availability(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, availability_id: uuid.UUID
) -> Availability:
    """Stop offering these hours. Visits already booked in them are not touched."""
    row = get_in_tenant(session, Availability, tenant_id=tenant_id, row_id=availability_id)
    if not isinstance(row, Availability) or row.clinician_id != actor_id:
        # Someone else's hours answer like missing ones.
        raise AvailabilityNotFoundError("Hours not found.")
    removed = Availability.model_validate(row)  # a copy to answer with
    session.delete(row)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.AVAILABILITY_REMOVE,
        entity_id=availability_id,
    )
    session.commit()
    return removed


def list_availability(
    session: Session, *, tenant_id: uuid.UUID, clinician_id: uuid.UUID
) -> list[Availability]:
    """One clinician's weekly hours, Monday first. No patient data, so no diary line."""
    statement = (
        tenant_select(Availability, tenant_id)
        .where(col(Availability.clinician_id) == clinician_id)
        .order_by(col(Availability.weekday), col(Availability.starts))
    )
    return list(session.exec(statement).all())


def _busy(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    clinician_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    unfinished = [status.value for status in ACTIVE_STATUSES]
    rows = session.exec(
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.clinician_id) == clinician_id)
        .where(col(Appointment.status).in_(unfinished))
        .where(col(Appointment.starts_at) < end)
        .where(col(Appointment.ends_at) > start)
    ).all()
    return [(row.starts_at, row.ends_at) for row in rows]


def free_slots(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    clinician_id: uuid.UUID,
    visit_type: str,
    from_day: date,
    days: int = 7,
    now: datetime | None = None,
) -> list[Slot]:
    """The clinician's free slots of one type, from a Lagos day, earliest first."""
    kind = _visit_type(visit_type)
    current = now or datetime.now(UTC)
    days = max(1, min(days, MAX_DAYS_SHOWN))
    published = list_availability(session, tenant_id=tenant_id, clinician_id=clinician_id)
    hours = [row for row in published if row.visit_type == kind]
    if not hours:
        return []

    window_start = datetime.combine(from_day, time.min, tzinfo=CLINIC_TIME)
    window_end = window_start + timedelta(days=days)
    busy = _busy(
        session, tenant_id=tenant_id, clinician_id=clinician_id, start=window_start, end=window_end
    )

    slots: list[Slot] = []
    for offset in range(days):
        day = from_day + timedelta(days=offset)
        for row in hours:
            if row.weekday != day.weekday():
                continue
            start = datetime.combine(day, row.starts, tzinfo=CLINIC_TIME)
            stop = datetime.combine(day, row.ends, tzinfo=CLINIC_TIME)
            step = timedelta(minutes=row.slot_minutes)
            while start + step <= stop:
                end = start + step
                taken = any(start < b_end and b_start < end for b_start, b_end in busy)
                if start >= current and not taken:
                    slots.append(
                        Slot(
                            starts_at=start.astimezone(UTC),
                            ends_at=end.astimezone(UTC),
                            branch_id=row.branch_id,
                            visit_type=kind,
                        )
                    )
                start = end
    return sorted(slots, key=lambda slot: slot.starts_at)


def is_free_slot(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    clinician_id: uuid.UUID,
    visit_type: str,
    starts_at: datetime,
    now: datetime | None = None,
) -> Slot | None:
    """The free slot starting exactly then, or None. For patients booking themselves."""
    day = starts_at.astimezone(CLINIC_TIME).date()
    for slot in free_slots(
        session,
        tenant_id=tenant_id,
        clinician_id=clinician_id,
        visit_type=visit_type,
        from_day=day,
        days=1,
        now=now,
    ):
        if slot.starts_at == starts_at.astimezone(UTC):
            return slot
    return None
