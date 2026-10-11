import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEvent(SQLModel, table=True):
    """One line in the access log. IDs and codes only: never names, phones or notes."""

    __tablename__ = "audit_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(index=True)
    actor_id: uuid.UUID
    patient_id: uuid.UUID | None = Field(default=None, index=True)
    action: str
    purpose: str | None = None
    occurred_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )