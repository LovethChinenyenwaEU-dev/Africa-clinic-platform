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

class StaffMfa(SQLModel, table=True):
    """A staff member's authenticator app (Week 11). One per person.

    The secret is pending until the person proves their app works with a first code
    (confirmed_at). last_step is the 30-second step of the last code used, so no code
    works twice. After five wrong codes in a row, sign-in waits until locked_until.
    """

    __tablename__ = "staff_mfa"

    staff_id: uuid.UUID = Field(foreign_key="staff.id", primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    secret: str
    confirmed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_step: int | None = None
    failed_attempts: int = 0
    locked_until: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class StaffBackupCode(SQLModel, table=True):
    """A one-time code for when the phone is lost. Only a keyed hash is kept."""

    __tablename__ = "staff_backup_code"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    staff_id: uuid.UUID = Field(foreign_key="staff.id", index=True)
    code_hash: str
    used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
