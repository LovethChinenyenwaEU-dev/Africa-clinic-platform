"""The notification console (Week 11 Step 7c): what the reminder worker did, for admins.

Which reminders went out, which are waiting, which failed and why, over some Lagos days
(by when each was due). IDs, codes and times only, like the reminder table itself: no
patient name or phone, so the admin (who has no patient access) can read it.

A failed reminder can be tried again while its visit is still booked and ahead: for
example after the front desk added the missing phone number, or the SMS provider is
back. It goes back in the queue with its attempts reset; the worker does the rest and
still checks consent and the phone number at send time.
"""
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.notifications.models import Reminder
from app.modules.notifications.statuses import ReminderStatus
from app.modules.scheduling.board import day_bounds
from app.modules.scheduling.models import Appointment

MAX_DAYS = 31
MAX_ROWS = 200  # newest first; the counts still cover every reminder in the days


class BadRangeError(ValueError):
    """The days asked for make no sense, or are too many."""


class ReminderNotFoundError(Exception):
    """No such reminder in this clinic."""


class CannotRetryError(Exception):
    """Only a failed reminder for a visit still booked and ahead can be tried again."""


@dataclass(frozen=True)
class ConsoleLine:
    reminder: Reminder
    visit_starts_at: datetime | None
    visit_type: str | None
    can_retry: bool


@dataclass(frozen=True)
class Console:
    from_day: date
    to_day: date
    counts: dict[str, int]  # every status, zero included
    failures: dict[str, int]  # last_error code -> how many, for failed and cancelled ones
    lines: list[ConsoleLine]
    more: bool  # more reminders than MAX_ROWS in these days


def _retryable(reminder: Reminder, visit: Appointment | None, now: datetime) -> bool:
    return (
        reminder.status == ReminderStatus.FAILED.value
        and visit is not None
        and visit.status == "booked"
        and visit.starts_at > now
    )


def _line(reminder: Reminder, visit: Appointment | None, now: datetime) -> ConsoleLine:
    return ConsoleLine(
        reminder=reminder,
        visit_starts_at=visit.starts_at if visit else None,
        visit_type=visit.visit_type if visit else None,
        can_retry=_retryable(reminder, visit, now),
    )


def reminder_console(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    from_day: date,
    to_day: date,
    status: ReminderStatus | None = None,
    now: datetime,
) -> Console:
    """Reminders due in these Lagos days (both included). Written in the audit log."""
    if from_day > to_day:
        raise BadRangeError("The first day must not come after the last day.")
    if (to_day - from_day).days + 1 > MAX_DAYS:
        raise BadRangeError(f"Choose at most {MAX_DAYS} days.")
    start, _ = day_bounds(from_day)
    _, end = day_bounds(to_day)

    in_days = list(
        session.exec(
            tenant_select(Reminder, tenant_id)
            .where(col(Reminder.due_at) >= start)
            .where(col(Reminder.due_at) < end)
            .order_by(col(Reminder.due_at).desc())
        ).all()
    )
    counts = Counter(r.status for r in in_days)
    failures = Counter(
        r.last_error
        for r in in_days
        if r.last_error
        and r.status in (ReminderStatus.FAILED.value, ReminderStatus.CANCELLED.value)
    )
    shown = [r for r in in_days if status is None or r.status == status.value]
    page = shown[:MAX_ROWS]

    visit_ids = {r.appointment_id for r in page}
    visits = {}
    if visit_ids:
        visits = {
            v.id: v
            for v in session.exec(
                tenant_select(Appointment, tenant_id).where(col(Appointment.id).in_(visit_ids))
            ).all()
        }
    lines = [_line(r, visits.get(r.appointment_id), now) for r in page]
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.REMINDER_LIST
    )
    session.commit()
    return Console(
        from_day=from_day,
        to_day=to_day,
        counts={s.value: counts.get(s.value, 0) for s in ReminderStatus},
        failures=dict(failures.most_common()),
        lines=lines,
        more=len(shown) > MAX_ROWS,
    )


def retry_reminder(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    reminder_id: uuid.UUID,
    now: datetime,
) -> Reminder:
    """Put a failed reminder back in the queue, due now, with its attempts reset."""
    reminder = get_in_tenant(session, Reminder, tenant_id=tenant_id, row_id=reminder_id)
    if reminder is None:
        raise ReminderNotFoundError(str(reminder_id))
    visit = get_in_tenant(
        session, Appointment, tenant_id=tenant_id, row_id=reminder.appointment_id
    )
    if reminder.status != ReminderStatus.FAILED.value:
        raise CannotRetryError("Only a failed reminder can be tried again.")
    if not _retryable(reminder, visit, now):
        raise CannotRetryError(
            "The visit is no longer booked and ahead, so no reminder is needed."
        )
    reminder.status = ReminderStatus.PENDING.value
    reminder.due_at = now
    reminder.attempts = 0
    reminder.last_error = None
    session.add(reminder)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.REMINDER_RETRY,
        entity_id=reminder.id,
    )
    session.commit()
    session.refresh(reminder)
    return reminder
