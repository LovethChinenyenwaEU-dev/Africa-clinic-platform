import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class Role(StrEnum):
    ADMIN = "admin"
    FRONT_DESK = "front_desk"
    NURSE = "nurse"
    DOCTOR = "doctor"
    BILLING = "billing"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Staff(SQLModel, table=True):
    """A person who works at a clinic and can log in."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    email: str = Field(unique=True, index=True)
    full_name: str
    role: str
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )