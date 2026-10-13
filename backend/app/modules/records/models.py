import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _time_column(*, nullable: bool = False) -> Column:
    """A column that stores a moment in time together with its time zone."""
    return Column(DateTime(timezone=True), nullable=nullable)


class Encounter(SQLModel, table=True):
    """One clinical contact with a patient. The folder that vitals, notes and diagnoses go in.

    IDs, codes and times only; the clinical content lives in its own tables.
    The id may be made by the device, so a record saved offline keeps the same id
    when it syncs.
    """

    __table_args__ = (
        # One encounter per visit, so a retried "start" can never open two.
        UniqueConstraint("appointment_id", name="uq_encounter_appointment"),
        # A patient's history, newest first.
        Index("ix_encounter_tenant_patient_opened_at", "tenant_id", "patient_id", "opened_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    appointment_id: uuid.UUID | None = Field(default=None, foreign_key="appointment.id")
    clinician_id: uuid.UUID = Field(foreign_key="staff.id")  # who opened it
    status: str  # see statuses.py
    opened_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())
    closed_at: datetime | None = Field(default=None, sa_column=_time_column(nullable=True))
    closed_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
