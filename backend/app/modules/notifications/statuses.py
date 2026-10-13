from enum import StrEnum


class ReminderStatus(StrEnum):
    PENDING = "pending"  # waiting for its due time, or for a retry
    SENT = "sent"  # the provider accepted it
    FAILED = "failed"  # gave up: retries used up, or the provider said never
    CANCELLED = "cancelled"  # the visit was cancelled, so nothing should go out


class ReminderChannel(StrEnum):
    SMS = "sms"
    WHATSAPP = "whatsapp"


# Statuses that are final: the sender must never touch these again.
FINAL_STATUSES = frozenset(
    {
        ReminderStatus.SENT,
        ReminderStatus.FAILED,
        ReminderStatus.CANCELLED,
    }
)
