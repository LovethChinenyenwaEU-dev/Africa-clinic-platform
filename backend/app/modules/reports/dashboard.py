"""The clinic dashboard (Week 11 Step 5): how the clinic is doing over a few days.

What the brief asks to see (P-11): wait time, no-shows, consultation completion, sync
failures, revenue and record-access events. Counts, rates and sums only: no patient
names, phones or notes, so the admin (who has no patient access) can read it.

How each number is worked out (the screen says it too):
- visits: appointments whose start time falls in the days chosen (Lagos days);
- no-show rate: of the booked (not walk-in) patients who were due, how many never came:
  no-shows / (no-shows + booked patients who checked in). Walk-ins cannot be no-shows;
- completion: of the patients who checked in, how many had their consultation completed;
- wait: from check-in to the start of the consultation, for visits that have both;
- revenue: payments received, approved refunds and invoices issued in those days;
- sync: offline entries that reached the server after sign-off (late), versions waiting
  for a clinician to choose (conflicts, as of now), offline registrations to review (now),
  reminders that went out or gave up, online payments that failed;
- record access: audit lines about a patient written by staff (not by the patient on
  their own page, not by the platform), and who wrote the most.
"""
import math
import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.tenant_scope import tenant_select
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import (
    PATIENT_PORTAL,
    SYSTEM_ACTOR_ID,
    AuditAction,
    add_audit_event,
)
from app.modules.billing.models import (
    Invoice,
    InvoiceStatus,
    OnlinePayment,
    OnlinePaymentStatus,
    Payment,
    Refund,
    RefundStatus,
)
from app.modules.identity.service import list_staff
from app.modules.notifications.models import Reminder
from app.modules.notifications.statuses import ReminderStatus
from app.modules.patients.models import Patient, ReviewStatus
from app.modules.records.models import (
    Allergy,
    ClinicalNote,
    FollowUp,
    Prescription,
    Problem,
    Referral,
    VitalSigns,
)
from app.modules.records.statuses import VersionStatus
from app.modules.scheduling.board import day_bounds, lagos_day
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import AppointmentKind, AppointmentStatus

MAX_DAYS = 92  # about three months: enough for a trend, small enough to answer quickly
LONG_WAIT_MINUTES = 60
TOP_STAFF = 10
UNKNOWN = "(name not found)"

# Records an offline device can send after sign-off (marked synced_late), and records
# that can hold a conflict between two devices.
LATE_CAPABLE = (VitalSigns, ClinicalNote, Prescription, FollowUp, Referral)
CONFLICT_CAPABLE = (Allergy, Problem, ClinicalNote, Prescription)
STILL_OPEN = (AppointmentStatus.BOOKED, AppointmentStatus.WAITING, AppointmentStatus.IN_CONSULT)


class BadRangeError(ValueError):
    """The days asked for make no sense, or are too many."""


@dataclass(frozen=True)
class Visits:
    total: int
    walk_ins: int
    done: int
    no_shows: int
    cancelled: int
    still_open: int  # booked, waiting or in consultation
    checked_in: int
    no_show_rate: float | None  # None when nobody was due
    completion_rate: float | None  # None when nobody checked in


@dataclass(frozen=True)
class Waits:
    measured: int
    median_minutes: float | None
    p90_minutes: float | None
    over_an_hour: int


@dataclass(frozen=True)
class MethodTotal:
    method: str
    count: int
    amount_kobo: int


@dataclass(frozen=True)
class Revenue:
    invoices_issued: int
    billed_kobo: int
    payments: int
    received_kobo: int
    refunds: int
    refunded_kobo: int
    by_method: list[MethodTotal]

    @property
    def net_kobo(self) -> int:
        return self.received_kobo - self.refunded_kobo


@dataclass(frozen=True)
class Sync:
    late_entries: int
    open_conflicts: int
    registrations_to_review: int
    reminders_sent: int
    reminders_failed: int
    online_payments_failed: int


@dataclass(frozen=True)
class StaffAccess:
    staff_id: uuid.UUID
    name: str
    events: int
    patients: int


@dataclass(frozen=True)
class RecordAccess:
    events: int
    patients: int
    by_staff: list[StaffAccess]


@dataclass(frozen=True)
class Day:
    day: date
    visits: int
    done: int
    no_shows: int
    median_wait_minutes: float | None
    received_kobo: int


@dataclass(frozen=True)
class Dashboard:
    from_day: date
    to_day: date
    visits: Visits
    waits: Waits
    revenue: Revenue
    sync: Sync
    record_access: RecordAccess
    days: list[Day]


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def percentile(values: list[float], share: float) -> float | None:
    """Nearest rank: the smallest value with at least this share of values at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(share * len(ordered)) - 1)], 1)


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def wait_minutes(rows: list[Appointment]) -> list[float]:
    """Check-in to consultation start, for the visits that have both."""
    return [
        max(0.0, (row.consult_started_at - row.checked_in_at).total_seconds() / 60)
        for row in rows
        if row.checked_in_at is not None and row.consult_started_at is not None
    ]


def count_visits(rows: list[Appointment]) -> Visits:
    statuses = Counter(row.status for row in rows)
    booked_and_came = sum(
        1
        for row in rows
        if row.kind == AppointmentKind.SCHEDULED.value and row.checked_in_at is not None
    )
    checked_in = sum(1 for row in rows if row.checked_in_at is not None)
    no_shows = statuses[AppointmentStatus.NO_SHOW.value]
    done = statuses[AppointmentStatus.DONE.value]
    return Visits(
        total=len(rows),
        walk_ins=sum(1 for row in rows if row.kind == AppointmentKind.WALK_IN.value),
        done=done,
        no_shows=no_shows,
        cancelled=statuses[AppointmentStatus.CANCELLED.value],
        still_open=sum(statuses[status.value] for status in STILL_OPEN),
        checked_in=checked_in,
        no_show_rate=_rate(no_shows, no_shows + booked_and_came),
        completion_rate=_rate(done, checked_in),
    )


def _between(statement, column, start: datetime, end: datetime):
    return statement.where(col(column) >= start).where(col(column) < end)


def _count(session: Session, model, tenant_id: uuid.UUID, *conditions) -> int:
    statement = select(func.count()).select_from(model).where(col(model.tenant_id) == tenant_id)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.exec(statement).one())


def _revenue(
    session: Session, tenant_id: uuid.UUID, start: datetime, end: datetime
) -> tuple[Revenue, list[Payment]]:
    payments = list(
        session.exec(_between(tenant_select(Payment, tenant_id), Payment.received_at, start, end))
    )
    approved = tenant_select(Refund, tenant_id).where(
        col(Refund.status) == RefundStatus.APPROVED.value
    )
    refunds = list(session.exec(_between(approved, Refund.decided_at, start, end)))
    issued_invoices = tenant_select(Invoice, tenant_id).where(
        col(Invoice.status) == InvoiceStatus.ISSUED.value
    )
    issued = list(session.exec(_between(issued_invoices, Invoice.issued_at, start, end)))

    counts: Counter[str] = Counter(payment.method for payment in payments)
    amounts: dict[str, int] = defaultdict(int)
    for payment in payments:
        amounts[payment.method] += payment.amount_kobo
    revenue = Revenue(
        invoices_issued=len(issued),
        billed_kobo=sum(invoice.total_kobo for invoice in issued),
        payments=len(payments),
        received_kobo=sum(amounts.values()),
        refunds=len(refunds),
        refunded_kobo=sum(refund.amount_kobo for refund in refunds),
        by_method=[MethodTotal(m, counts[m], amounts[m]) for m in sorted(counts)],
    )
    return revenue, payments


def _sync(session: Session, tenant_id: uuid.UUID, start: datetime, end: datetime) -> Sync:
    late = sum(
        _count(
            session,
            model,
            tenant_id,
            col(model.synced_late).is_(True),
            col(model.recorded_at) >= start,
            col(model.recorded_at) < end,
        )
        for model in LATE_CAPABLE
    )
    conflicts = sum(
        _count(session, model, tenant_id, col(model.version_status) == VersionStatus.CONFLICT.value)
        for model in CONFLICT_CAPABLE
    )
    return Sync(
        late_entries=late,
        open_conflicts=conflicts,
        registrations_to_review=_count(
            session,
            Patient,
            tenant_id,
            col(Patient.review_status) == ReviewStatus.NEEDS_REVIEW.value,
        ),
        reminders_sent=_count(
            session,
            Reminder,
            tenant_id,
            col(Reminder.status) == ReminderStatus.SENT.value,
            col(Reminder.sent_at) >= start,
            col(Reminder.sent_at) < end,
        ),
        # A reminder that gave up keeps the time of its last try in due_at.
        reminders_failed=_count(
            session,
            Reminder,
            tenant_id,
            col(Reminder.status) == ReminderStatus.FAILED.value,
            col(Reminder.due_at) >= start,
            col(Reminder.due_at) < end,
        ),
        online_payments_failed=_count(
            session,
            OnlinePayment,
            tenant_id,
            col(OnlinePayment.status) == OnlinePaymentStatus.FAILED.value,
            col(OnlinePayment.completed_at) >= start,
            col(OnlinePayment.completed_at) < end,
        ),
    )


def _record_access(
    session: Session, tenant_id: uuid.UUID, start: datetime, end: datetime
) -> RecordAccess:
    statement = (
        select(AuditEvent.actor_id, AuditEvent.patient_id)
        .where(col(AuditEvent.tenant_id) == tenant_id)
        .where(col(AuditEvent.patient_id).is_not(None))
        .where(col(AuditEvent.actor_id) != SYSTEM_ACTOR_ID)
        .where(col(AuditEvent.purpose).is_distinct_from(PATIENT_PORTAL))
    )
    rows = session.exec(_between(statement, AuditEvent.occurred_at, start, end)).all()
    events: Counter[uuid.UUID] = Counter()
    patients: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for actor_id, patient_id in rows:
        events[actor_id] += 1
        patients[actor_id].add(patient_id)
    names = {staff.id: staff.full_name for staff in list_staff(session, tenant_id=tenant_id)}
    by_staff = sorted(
        (
            StaffAccess(actor, names.get(actor, UNKNOWN), count, len(patients[actor]))
            for actor, count in events.items()
        ),
        key=lambda row: (-row.events, row.name),
    )
    return RecordAccess(
        events=len(rows),
        patients=len({patient_id for _, patient_id in rows}),
        by_staff=by_staff[:TOP_STAFF],
    )


def _days(
    from_day: date, to_day: date, visits: list[Appointment], payments: list[Payment]
) -> list[Day]:
    """One line per Lagos day, for the trend."""
    by_day: dict[date, list[Appointment]] = defaultdict(list)
    for row in visits:
        by_day[lagos_day(row.starts_at)].append(row)
    received: dict[date, int] = defaultdict(int)
    for payment in payments:
        received[lagos_day(payment.received_at)] += payment.amount_kobo
    days = []
    day = from_day
    while day <= to_day:
        rows = by_day.get(day, [])
        statuses = Counter(row.status for row in rows)
        days.append(
            Day(
                day=day,
                visits=len(rows),
                done=statuses[AppointmentStatus.DONE.value],
                no_shows=statuses[AppointmentStatus.NO_SHOW.value],
                median_wait_minutes=median(wait_minutes(rows)),
                received_kobo=received.get(day, 0),
            )
        )
        day += timedelta(days=1)
    return days


def check_range(from_day: date, to_day: date) -> None:
    if from_day > to_day:
        raise BadRangeError("The first day must not come after the last day.")
    if (to_day - from_day).days + 1 > MAX_DAYS:
        raise BadRangeError(f"Choose at most {MAX_DAYS} days.")


def clinic_dashboard(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    from_day: date,
    to_day: date,
) -> Dashboard:
    """The clinic's numbers for these Lagos days (both included). Written in the diary."""
    check_range(from_day, to_day)
    start, _ = day_bounds(from_day)
    _, end = day_bounds(to_day)

    visits = list(
        session.exec(
            _between(tenant_select(Appointment, tenant_id), Appointment.starts_at, start, end)
        )
    )
    waits = wait_minutes(visits)
    revenue, payments = _revenue(session, tenant_id, start, end)

    result = Dashboard(
        from_day=from_day,
        to_day=to_day,
        visits=count_visits(visits),
        waits=Waits(
            measured=len(waits),
            median_minutes=median(waits),
            p90_minutes=percentile(waits, 0.9),
            over_an_hour=sum(1 for wait in waits if wait > LONG_WAIT_MINUTES),
        ),
        revenue=revenue,
        sync=_sync(session, tenant_id, start, end),
        record_access=_record_access(session, tenant_id, start, end),
        days=_days(from_day, to_day, visits, payments),
    )
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.REPORT_VIEW
    )
    session.commit()
    return result
