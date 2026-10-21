import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _time_column(*, nullable: bool = False) -> Column:
    return Column(DateTime(timezone=True), nullable=nullable)


class PatientLoginCode(SQLModel, table=True):
    """A one-time sign-in code sent by SMS. Only a keyed hash of the code is kept.

    Short-lived (10 minutes), used once, and given up after 5 wrong tries.
    """

    __tablename__ = "patient_login_code"
    __table_args__ = (
        Index("ix_patient_login_code_phone_created", "tenant_id", "phone", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    phone: str  # standard form, for the "how many codes lately" limit
    code_hash: str
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())
    expires_at: datetime = Field(sa_column=_time_column())
    used_at: datetime | None = Field(default=None, sa_column=_time_column(nullable=True))
