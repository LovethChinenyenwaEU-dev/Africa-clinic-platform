import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class ConsentPurpose(StrEnum):
    TREATMENT = "treatment"
    REMINDERS = "reminders"
    TELECONSULT = "teleconsult"
    REFERRAL_SHARING = "referral_sharing"


class GrantedBy(StrEnum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"


def utcnow() -> datetime:
    return datetime.now(UTC)


class ConsentText(SQLModel, table=True):
    """The wording a clinic shows for one purpose. A new wording is a new version."""

    __tablename__ = "consent_text"
    __table_args__ = (
        UniqueConstraint("tenant_id", "purpose", "version", name="uq_consent_text_version"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    purpose: str
    version: int
    body: str
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Consent(SQLModel, table=True):
    """A patient's permission for one purpose. Revoking stamps the row; it never deletes it."""

    __table_args__ = (Index("ix_consent_patient_purpose", "patient_id", "purpose"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    purpose: str
    consent_text_id: uuid.UUID = Field(foreign_key="consent_text.id")
    granted_by: str
    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")
    granted_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")