import uuid
from datetime import UTC, datetime, time

from sqlalchemy import ARRAY, Column, DateTime, Index, String, Time
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _time_column(*, nullable: bool = False) -> Column:
    """A column that stores a moment in time together with its time zone."""
    return Column(DateTime(timezone=True), nullable=nullable)


class Appointment(SQLModel, table=True):
    """One visit: booked ahead, or a walk-in. Only IDs, codes and times. No free text."""

    __table_args__ = (
        Index("ix_appointment_tenant_starts_at", "tenant_id", "starts_at"),
        Index("ix_appointment_clinician_starts_at", "clinician_id", "starts_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    branch_id: uuid.UUID = Field(foreign_key="branch.id")
    patient_id: uuid.UUID = Field(foreign_key="patient.id", index=True)
    clinician_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    kind: str  # scheduled or walk_in
    visit_type: str  # in_person or teleconsult
    status: str  # see statuses.py
    starts_at: datetime = Field(sa_column=_time_column())
    ends_at: datetime = Field(sa_column=_time_column())
    checked_in_at: datetime | None = Field(default=None, sa_column=_time_column(nullable=True))
    consult_started_at: datetime | None = Field(
        default=None, sa_column=_time_column(nullable=True)
    )
    completed_at: datetime | None = Field(default=None, sa_column=_time_column(nullable=True))
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())

class Triage(SQLModel, table=True):
    """How urgent a waiting patient is, and which danger signs they have. Codes only.

    Never edited: triaging again (the patient got worse, or better) adds a new row,
    and the newest one counts. The history shows who decided what, and when.
    """

    __table_args__ = (Index("ix_triage_appointment_recorded_at", "appointment_id", "recorded_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id")
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    level: str  # see statuses.TriageLevel
    red_flags: list[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(String), nullable=False)
    )
    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())


class Availability(SQLModel, table=True):
    """A clinician's weekly hours: "Mondays 09:00-13:00, remote, 15-minute slots" (FR-C1).

    Times are Lagos wall-clock times (no daylight saving in Nigeria, so they never
    shift). A clinician publishes their own hours; nothing about patients is here.
    """

    __table_args__ = (Index("ix_availability_clinician_weekday", "clinician_id", "weekday"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    clinician_id: uuid.UUID = Field(foreign_key="staff.id")
    branch_id: uuid.UUID = Field(foreign_key="branch.id")  # where (or for whom) they work
    weekday: int  # 0 Monday ... 6 Sunday
    starts: time = Field(sa_column=Column(Time(), nullable=False))  # Lagos time
    ends: time = Field(sa_column=Column(Time(), nullable=False))
    visit_type: str  # in_person or teleconsult (statuses.VisitType)
    slot_minutes: int
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())
