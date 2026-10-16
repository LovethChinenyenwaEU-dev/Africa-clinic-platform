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


class ConsultRoom(SQLModel, table=True):
    """The room for one remote visit: which video provider, the random room name, and
    whether the call is now on video, audio or text (FR-C3, FR-C4). IDs and codes only."""

    __tablename__ = "consult_room"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id", unique=True)
    provider: str  # jitsi, fake or none (video.py)
    room_name: str  # long and random; never a name or ID
    mode: str  # video, audio or text
    opened_by_id: uuid.UUID = Field(foreign_key="staff.id")
    opened_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class ConsultModeChange(SQLModel, table=True):
    """Every switch between video, audio and text, and why (FR-C4). Never edited."""

    __tablename__ = "consult_mode_change"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id", index=True)
    from_mode: str
    to_mode: str
    reason: str  # poor_connection, patient_choice or clinician_choice
    changed_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    changed_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class ConsultMessage(SQLModel, table=True):
    """One chat message in a remote visit. Health information: never logged.

    Never edited or deleted. The device makes the ID, so a re-sent message appears once.
    """

    __tablename__ = "consult_message"
    __table_args__ = (Index("ix_consult_message_appointment_sent_at", "appointment_id", "sent_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id")
    sender: str  # staff or patient
    sender_staff_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    body: str
    sent_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
