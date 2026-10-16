import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

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


class VitalSigns(SQLModel, table=True):
    """One set of measurements taken together. Every reading is optional, but a set has one.

    Never edited: a correction is a new row that points at the one it replaces, and
    the old row is only marked superseded.
    """

    __tablename__ = "vital_signs"
    __table_args__ = (
        Index("ix_vital_signs_encounter_recorded_at", "encounter_id", "recorded_at"),
        Index(
            "ix_vital_signs_tenant_patient_measured_at", "tenant_id", "patient_id", "measured_at"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    encounter_id: uuid.UUID = Field(foreign_key="encounter.id")
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    status: str  # see statuses.py
    replaces_id: uuid.UUID | None = Field(default=None, foreign_key="vital_signs.id")

    systolic_mmhg: int | None = None
    diastolic_mmhg: int | None = None
    pulse_bpm: int | None = None
    respiratory_rate: int | None = None  # breaths per minute
    spo2_pct: int | None = None
    temperature_c: Decimal | None = Field(default=None, max_digits=4, decimal_places=1)
    weight_kg: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    height_cm: Decimal | None = Field(default=None, max_digits=4, decimal_places=1)

    measured_at: datetime = Field(sa_column=_time_column())  # when taken, maybe offline
    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())


class Allergy(SQLModel, table=True):
    """Something the patient reacts to. Belongs to the patient, so every visit sees it.

    Never edited: a change is a new row that points at the one it replaces.
    """

    __table_args__ = (
        Index("ix_allergy_tenant_patient_status", "tenant_id", "patient_id", "version_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    encounter_id: uuid.UUID = Field(foreign_key="encounter.id")  # the visit it was recorded in
    version_status: str  # current, superseded or conflict (statuses.py)
    replaces_id: uuid.UUID | None = Field(default=None, foreign_key="allergy.id")

    substance: str  # what the patient reacts to, for example penicillin
    reaction: str | None = None  # what happens, for example rash
    severity: str  # see statuses.py
    clinical_status: str  # see statuses.py

    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())


class Problem(SQLModel, table=True):
    """A condition or diagnosis. Belongs to the patient, so every visit sees it.

    Never edited: a change is a new row that points at the one it replaces.
    """

    __table_args__ = (
        Index("ix_problem_tenant_patient_status", "tenant_id", "patient_id", "version_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    encounter_id: uuid.UUID = Field(foreign_key="encounter.id")  # the visit it was recorded in
    version_status: str  # current, superseded or conflict (statuses.py)
    replaces_id: uuid.UUID | None = Field(default=None, foreign_key="problem.id")

    category: str  # see statuses.py
    description: str  # in the clinician's words, for example uncomplicated malaria
    code: str | None = None  # optional ICD-10 code, for example B54
    clinical_status: str  # see statuses.py
    onset_date: date | None = None

    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())


class ClinicalNote(SQLModel, table=True):
    """A clinician's own words about a visit. The most sensitive text we hold.

    Never edited: an amendment is a new row that points at the one it replaces,
    and only the author may amend.
    """

    __tablename__ = "clinical_note"
    __table_args__ = (
        Index("ix_clinical_note_encounter_recorded_at", "encounter_id", "recorded_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    encounter_id: uuid.UUID = Field(foreign_key="encounter.id")
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    version_status: str  # current, superseded or conflict (statuses.py)
    replaces_id: uuid.UUID | None = Field(default=None, foreign_key="clinical_note.id")

    kind: str  # see statuses.py
    body: str

    recorded_by_id: uuid.UUID = Field(foreign_key="staff.id")  # the author
    recorded_at: datetime = Field(default_factory=utcnow, sa_column=_time_column())
