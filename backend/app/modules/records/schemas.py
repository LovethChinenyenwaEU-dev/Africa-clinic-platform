"""The forms the records endpoints accept and the answers they give.

There is never a clinic box: the clinic always comes from the logged-in person.
Every `id` in a form is optional: a device working offline sends the ID it made,
so a retried request is recognised and changes nothing.

Size limits here only stop huge payloads; the real rules live in the services.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OpenEncounter(BaseModel):
    id: uuid.UUID | None = None
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None


class EncounterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    clinician_id: uuid.UUID
    status: str
    opened_at: datetime
    closed_at: datetime | None
    closed_by_id: uuid.UUID | None


class Readings(BaseModel):
    systolic_mmhg: int | None = None
    diastolic_mmhg: int | None = None
    pulse_bpm: int | None = None
    respiratory_rate: int | None = None
    spo2_pct: int | None = None
    temperature_c: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None


class RecordVitals(Readings):
    id: uuid.UUID | None = None
    measured_at: datetime | None = None  # when taken; must include a time zone


class CorrectVitals(Readings):
    id: uuid.UUID | None = None  # the ID of the correction


class VitalsResponse(BaseModel):
    """Decimals come back as text, for example "37.5", so no precision is lost."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    replaces_id: uuid.UUID | None
    systolic_mmhg: int | None
    diastolic_mmhg: int | None
    pulse_bpm: int | None
    respiratory_rate: int | None
    spo2_pct: int | None
    temperature_c: Decimal | None
    weight_kg: Decimal | None
    height_cm: Decimal | None
    measured_at: datetime
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    synced_late: bool


class AllergyForm(BaseModel):
    id: uuid.UUID | None = None
    substance: str = Field(max_length=1000)
    reaction: str | None = Field(default=None, max_length=2000)
    severity: str = Field(default="unknown", max_length=20)
    clinical_status: str = Field(default="active", max_length=20)


class ReviseAllergy(AllergyForm):
    encounter_id: uuid.UUID  # the open visit the change is made in


class AllergyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    version_status: str
    replaces_id: uuid.UUID | None
    substance: str
    reaction: str | None
    severity: str
    clinical_status: str
    recorded_by_id: uuid.UUID
    recorded_at: datetime


class ProblemForm(BaseModel):
    id: uuid.UUID | None = None
    description: str = Field(max_length=2000)
    category: str = Field(default="problem_list", max_length=30)
    code: str | None = Field(default=None, max_length=20)
    clinical_status: str = Field(default="active", max_length=20)
    onset_date: date | None = None


class ReviseProblem(ProblemForm):
    encounter_id: uuid.UUID  # the open visit the change is made in


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    version_status: str
    replaces_id: uuid.UUID | None
    category: str
    description: str
    code: str | None
    clinical_status: str
    onset_date: date | None
    recorded_by_id: uuid.UUID
    recorded_at: datetime


class WriteNote(BaseModel):
    id: uuid.UUID | None = None
    kind: str = Field(max_length=20)
    body: str = Field(max_length=20_000)
    written_at: datetime | None = None  # when written on the device; must include a time zone


class AmendNote(BaseModel):
    id: uuid.UUID | None = None  # the ID of the amendment
    body: str = Field(max_length=20_000)


class ResolveConflict(BaseModel):
    """Which version to keep: `this` (the conflict in the URL) or `current` (the one in use).

    Choosing twice is harmless: the second answers 409, because nothing is in conflict.
    """

    keep: Literal["this", "current"]


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    version_status: str
    replaces_id: uuid.UUID | None
    kind: str
    body: str
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    written_at: datetime
    synced_late: bool


class PrescriptionForm(BaseModel):
    id: uuid.UUID | None = None
    medicine: str = Field(max_length=400)
    strength: str | None = Field(default=None, max_length=100)
    dose: str = Field(max_length=100)
    route: str = Field(default="oral", max_length=20)
    frequency: str = Field(max_length=160)
    duration: str = Field(max_length=100)
    instructions: str | None = Field(default=None, max_length=1000)
    written_at: datetime | None = None  # when written on the device; must include a time zone


class RevisePrescription(BaseModel):
    """The whole prescription as it should now read, with its status (active, stopped,
    entered_in_error). `id` is the ID of the new version."""

    id: uuid.UUID | None = None
    medicine: str = Field(max_length=400)
    strength: str | None = Field(default=None, max_length=100)
    dose: str = Field(max_length=100)
    route: str = Field(default="oral", max_length=20)
    frequency: str = Field(max_length=160)
    duration: str = Field(max_length=100)
    instructions: str | None = Field(default=None, max_length=1000)
    clinical_status: str = Field(default="active", max_length=20)


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    version_status: str
    replaces_id: uuid.UUID | None
    medicine: str
    strength: str | None
    dose: str
    route: str
    frequency: str
    duration: str
    instructions: str | None
    clinical_status: str
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    written_at: datetime
    synced_late: bool


class PlanFollowUp(BaseModel):
    id: uuid.UUID | None = None
    due_date: date  # a Lagos calendar day
    visit_type: str = Field(default="in_person", max_length=20)
    instructions: str | None = Field(default=None, max_length=1000)
    written_at: datetime | None = None


class FollowUpResponse(BaseModel):
    """For clinicians: with the instructions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    due_date: date
    visit_type: str
    instructions: str | None
    status: str
    appointment_id: uuid.UUID | None
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    synced_late: bool


class FollowUpDue(BaseModel):
    """For front desk: who, when and what kind of visit. No clinical instructions."""

    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    due_date: date
    visit_type: str
    status: str


class MarkBooked(BaseModel):
    appointment_id: uuid.UUID | None = None  # the visit booked for it, if known


class WriteReferral(BaseModel):
    id: uuid.UUID | None = None
    to_name: str = Field(max_length=400)
    specialty: str | None = Field(default=None, max_length=200)
    urgency: str = Field(default="routine", max_length=20)
    reason: str = Field(max_length=4000)
    written_at: datetime | None = None


class ReferralResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    to_name: str
    specialty: str | None
    urgency: str
    reason: str
    status: str
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    written_at: datetime
    synced_late: bool


class SummaryText(BaseModel):
    id: uuid.UUID | None = None  # for a new draft: made by the device
    body: str = Field(max_length=8000)  # the service allows 4000 after trimming


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    body: str
    status: str  # draft, approved or withdrawn
    drafted_by_id: uuid.UUID
    drafted_at: datetime
    updated_at: datetime
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    withdrawn_by_id: uuid.UUID | None
    withdrawn_at: datetime | None
