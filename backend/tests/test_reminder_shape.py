from app.modules.notifications.models import Reminder
from app.modules.notifications.statuses import FINAL_STATUSES, ReminderStatus

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "appointment_id",
    "channel",
    "status",
    "due_at",
    "attempts",
    "last_error",
    "provider_message_id",
    "sent_at",
    "created_at",
}


def test_reminder_table_holds_no_phone_numbers_or_message_text():
    """If someone adds a phone or body column, this fails and they must stop and think."""
    assert set(Reminder.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_only_pending_reminders_can_still_be_sent():
    assert FINAL_STATUSES == {
        ReminderStatus.SENT,
        ReminderStatus.FAILED,
        ReminderStatus.CANCELLED,
    }
    assert ReminderStatus.PENDING not in FINAL_STATUSES
