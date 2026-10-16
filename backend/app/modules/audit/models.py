import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEvent(SQLModel, table=True):
    """One line in the access log. IDs and codes only: never names, phones or notes."""

    __tablename__ = "audit_event"
    __table_args__ = (
        # The admin filters: newest first, optionally for one staff member.
        Index("ix_audit_event_tenant_occurred_at", "tenant_id", "occurred_at"),
        Index("ix_audit_event_tenant_actor_occurred_at", "tenant_id", "actor_id", "occurred_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(index=True)
    actor_id: uuid.UUID
    patient_id: uuid.UUID | None = Field(default=None, index=True)
    entity_id: uuid.UUID | None = None  # which note, vitals set, encounter... was touched
    device_id: uuid.UUID | None = None  # which device (browser) it came from; None if unknown
    action: str
    purpose: str | None = None
    occurred_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )