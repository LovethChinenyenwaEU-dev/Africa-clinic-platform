import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class InterestRequest(SQLModel, table=True):
    """One "Register interest" form. Personal data of the person asking (not patients):
    kept for a year, then deleted by the worker (see service.purge_old_interest)."""

    __tablename__ = "interest_request"
    __table_args__ = (
        Index("ix_interest_request_created_at", "created_at"),
        Index("ix_interest_request_email_created_at", "email", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str
    email: str  # lower case
    phone: str | None = None
    organisation: str
    role: str
    message: str | None = None
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
