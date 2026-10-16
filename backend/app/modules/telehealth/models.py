import uuid
from datetime import UTC, datetime

from sqlalchemy import ARRAY, Column, DateTime, Index, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class TeleconsultIntake(SQLModel, table=True):
    """Before a remote visit: why the patient wants it, and the danger-sign screen (FR-C2).

    A danger sign means the outcome is "escalated": remote care is not safe, the patient
    is advised to come in person, and the remote visit cannot start (FR-C6). Otherwise
    the outcome is "ready" and the patient joins the remote waiting room.

    Never edited: answering again adds a row, and the newest counts. The reason is the
    patient's own words, health information: never put in logs or error messages.
    """

    __tablename__ = "teleconsult_intake"
    __table_args__ = (
        Index("ix_teleconsult_intake_appointment_recorded_at", "appointment_id", "recorded_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id")
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    reason: str
    red_flags: list[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(String), nullable=False)
    )
    outcome: str  # ready or escalated
    source: str  # staff (on the phone, at the desk) or patient (patient web, Step 8)
    recorded_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    recorded_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
