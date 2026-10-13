"""Send reminders that are due, through whichever adapter is plugged in.

Each reminder is locked, sent and saved on its own. So if the worker dies
halfway, the ones already sent stay sent, and two workers running at once never
pick up the same reminder.

Nothing here logs a phone number or message text.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.modules.audit.service import SYSTEM_ACTOR_ID, AuditAction, add_audit_event
from app.modules.consent.service import has_active_consent
from app.modules.notifications.adapters import MessageAdapter, OutgoingMessage, ProviderError
from app.modules.notifications.messages import reminder_text
from app.modules.notifications.models import Reminder
from app.modules.notifications.statuses import ReminderStatus
from app.modules.patients.service import get_reminder_phone
from app.modules.scheduling.service import get_appointment

MAX_ATTEMPTS = 5
# Wait after attempt 1, 2, 3, 4. A fifth failure is final.
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
)
BATCH_SIZE = 50
REMINDER_CONSENT_PURPOSE = "reminders"  # one of the consent module's purposes


@dataclass
class SendRun:
    """What one run did. Counts only, safe to log."""

    sent: int = 0
    retrying: int = 0
    failed: int = 0
    cancelled: int = 0


def _next_due(
    session: Session, *, now: datetime, tenant_id: uuid.UUID | None
) -> Reminder | None:
    """The oldest due reminder that no other worker is holding right now."""
    statement = (
        select(Reminder)
        .where(col(Reminder.status) == ReminderStatus.PENDING.value)
        .where(col(Reminder.due_at) <= now)
        .order_by(col(Reminder.due_at))
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if tenant_id is not None:
        statement = statement.where(col(Reminder.tenant_id) == tenant_id)
    return session.exec(statement).first()


def _send_one(
    session: Session, reminder: Reminder, *, adapter: MessageAdapter, now: datetime
) -> str:
    """Try one reminder and record the outcome on it. Returns the SendRun field to count."""
    appointment = get_appointment(
        session, tenant_id=reminder.tenant_id, appointment_id=reminder.appointment_id
    )
    # Checked in, cancelled, no-show or already started: a reminder would only confuse.
    if appointment is None or appointment.status != "booked" or appointment.starts_at <= now:
        reminder.status = ReminderStatus.CANCELLED.value
        reminder.last_error = "visit_not_upcoming"
        return "cancelled"

    # Checked now, not at booking, so consent taken back after booking is respected.
    # Without consent we do not even look up the phone number.
    if not has_active_consent(
        session,
        tenant_id=reminder.tenant_id,
        patient_id=appointment.patient_id,
        purpose=REMINDER_CONSENT_PURPOSE,
    ):
        reminder.status = ReminderStatus.CANCELLED.value
        reminder.last_error = "no_consent"
        return "cancelled"

    phone = get_reminder_phone(
        session, tenant_id=reminder.tenant_id, patient_id=appointment.patient_id
    )
    if phone is None:
        reminder.status = ReminderStatus.FAILED.value
        reminder.last_error = "no_phone"
        return "failed"

    message = OutgoingMessage(
        to=phone,
        body=reminder_text(appointment.starts_at, appointment.visit_type),
        channel=reminder.channel,
    )
    reminder.attempts += 1
    try:
        receipt = adapter.send(message)
    except ProviderError as error:
        reminder.last_error = "provider_unavailable" if error.retryable else "provider_rejected"
        if error.retryable and reminder.attempts < MAX_ATTEMPTS:
            reminder.due_at = now + RETRY_DELAYS[reminder.attempts - 1]
            return "retrying"
        reminder.status = ReminderStatus.FAILED.value
        return "failed"

    reminder.status = ReminderStatus.SENT.value
    reminder.provider_message_id = receipt.provider_message_id
    reminder.sent_at = now
    reminder.last_error = None
    # The phone number just went to an outside company, so the diary records it.
    add_audit_event(
        session,
        tenant_id=reminder.tenant_id,
        actor_id=SYSTEM_ACTOR_ID,
        action=AuditAction.REMINDER_SEND,
        patient_id=appointment.patient_id,
    )
    return "sent"


def send_due_reminders(
    session: Session,
    *,
    adapter: MessageAdapter,
    now: datetime | None = None,
    tenant_id: uuid.UUID | None = None,
    batch_size: int = BATCH_SIZE,
) -> SendRun:
    """Send up to batch_size due reminders. tenant_id limits the run to one clinic."""
    current = now or datetime.now(UTC)
    run = SendRun()
    for _ in range(batch_size):
        reminder = _next_due(session, now=current, tenant_id=tenant_id)
        if reminder is None:
            break
        outcome = _send_one(session, reminder, adapter=adapter, now=current)
        session.add(reminder)
        session.commit()
        setattr(run, outcome, getattr(run, outcome) + 1)
    return run
