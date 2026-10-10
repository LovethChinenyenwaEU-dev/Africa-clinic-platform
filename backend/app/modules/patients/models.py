import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, SQLModel


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Patient(SQLModel, table=True):
    """A person who receives care at a clinic. This is personal health information."""

    __table_args__ = (Index("ix_patient_tenant_phone", "tenant_id", "phone"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    full_name: str
    date_of_birth: date
    sex: str
    phone: str | None = None
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )