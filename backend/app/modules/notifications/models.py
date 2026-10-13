import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _time_column(*, nullable: bool = False) -> Column:
    """A column that stores a moment in time together with its time zone."""
    return Column(DateTime(timezone=True), nullable=nullable)


class Reminder(SQLModel, table=True):
    """One reminder for one visit on one channel.

    IDs, codes, counts and times only. The phone number and the message text are
    looked up at send time and never stored here, so this table holds no PHI.
    """

    __table_args__ = (
        # One reminder per visit per channel, so a retried booking can never queue two.
        UniqueConstraint("appointment_id", "channel", name="uq_reminder_appointment_channel"),
        # The sender asks "which pending reminders are due now?" on every run.
        Index("ix_reminder_status_due_at", "status", "due_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id", index=True)
    channel: str  # see statuses.py
    status: str  # see statuses.py
    due_at: datetime = Field(sa_column=_time_column())  # next time to try sending
    attempts: int = 0
    last_error: str | None = None  # a short code like "provider_unavailable", never raw text
    provider_message_id: str | None = None
    sent_at: datetime | None = Field(default=None, sa_column=_time_column(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())
