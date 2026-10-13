"""Public door of the notifications module.

Other modules call these functions, never the models directly. None of them
commit: the caller commits, so a visit and its reminder are saved together or
not at all.
"""
import uuid
from datetime import datetime, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.notifications.models import Reminder
from app.modules.notifications.statuses import ReminderChannel, ReminderStatus

REMINDER_LEAD = timedelta(hours=24)


def reminder_due_at(starts_at: datetime, now: datetime) -> datetime:
    """24 hours before the visit, or right away if the visit is sooner than that."""
    return max(starts_at - REMINDER_LEAD, now)


def _reminders_for(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> list[Reminder]:
    statement = tenant_select(Reminder, tenant_id).where(
        col(Reminder.appointment_id) == appointment_id
    )
    return list(session.exec(statement).all())


def schedule_reminder(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    starts_at: datetime,
    now: datetime,
) -> Reminder:
    """Queue an SMS reminder for a newly booked visit."""
    reminder = Reminder(
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        channel=ReminderChannel.SMS.value,
        status=ReminderStatus.PENDING.value,
        due_at=reminder_due_at(starts_at, now),
    )
    session.add(reminder)
    return reminder


def cancel_reminders(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> None:
    """The visit is off: make sure nothing still waiting goes out."""
    for reminder in _reminders_for(session, tenant_id=tenant_id, appointment_id=appointment_id):
        if reminder.status == ReminderStatus.PENDING.value:
            reminder.status = ReminderStatus.CANCELLED.value
            session.add(reminder)


def reschedule_reminders(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    starts_at: datetime,
    now: datetime,
) -> None:
    """The visit moved: remind about the new time, even if the old one was already sent."""
    for reminder in _reminders_for(session, tenant_id=tenant_id, appointment_id=appointment_id):
        if reminder.status == ReminderStatus.CANCELLED.value:
            continue
        reminder.status = ReminderStatus.PENDING.value
        reminder.due_at = reminder_due_at(starts_at, now)
        reminder.attempts = 0
        reminder.last_error = None
        reminder.provider_message_id = None
        reminder.sent_at = None
        session.add(reminder)
