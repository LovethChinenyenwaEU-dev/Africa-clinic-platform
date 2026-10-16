import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class IdempotencyRecord(SQLModel, table=True):
    """The answer given to one write, kept so a repeat of it gets the same answer.

    The answer can contain clinical text, so records are deleted after a day
    (see service.purge_old_records) and are only ever replayed to the same person.
    """

    __tablename__ = "idempotency_record"
    __table_args__ = (
        # One key per person per clinic: nobody can replay someone else's answer.
        UniqueConstraint("tenant_id", "staff_id", "key", name="uq_idempotency_key"),
        Index("ix_idempotency_record_created_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id")
    staff_id: uuid.UUID = Field(foreign_key="staff.id")
    key: str
    request_hash: str  # what was sent: same key with a different request is refused
    status_code: int
    response_body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
