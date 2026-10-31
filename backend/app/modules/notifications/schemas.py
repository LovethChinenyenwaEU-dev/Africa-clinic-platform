import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ReminderLineResponse(BaseModel):
    """One reminder. IDs, codes and times only: no patient name or phone."""

    id: uuid.UUID
    appointment_id: uuid.UUID
    channel: str
    status: str
    due_at: datetime
    attempts: int
    last_error: str | None
    sent_at: datetime | None
    visit_starts_at: datetime | None
    visit_type: str | None
    can_retry: bool


class ReminderConsoleResponse(BaseModel):
    from_day: date
    to_day: date
    counts: dict[str, int]
    failures: dict[str, int]
    lines: list[ReminderLineResponse]
    more: bool


class ReminderRetriedResponse(BaseModel):
    id: uuid.UUID
    status: str
    due_at: datetime
