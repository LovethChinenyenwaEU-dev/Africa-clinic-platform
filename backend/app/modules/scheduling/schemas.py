import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class BookAppointment(BaseModel):
    """The form for booking a visit. There is no clinic box: it comes from the guard."""

    patient_id: uuid.UUID
    branch_id: uuid.UUID
    clinician_id: uuid.UUID
    starts_at: datetime  # must include a time zone, for example 2026-11-02T09:00:00+01:00
    duration_minutes: int = Field(default=30, ge=1, le=1440)
    visit_type: str = Field(default="in_person", max_length=20)


class WalkInRegistration(BaseModel):
    patient_id: uuid.UUID
    branch_id: uuid.UUID
    clinician_id: uuid.UUID | None = None
    duration_minutes: int = Field(default=30, ge=1, le=1440)


class RescheduleAppointment(BaseModel):
    starts_at: datetime
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)


class AppointmentResponse(BaseModel):
    """What we say about a visit. Clinic and staff-who-created IDs stay inside."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    branch_id: uuid.UUID
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    starts_at: datetime
    ends_at: datetime
    checked_in_at: datetime | None
    consult_started_at: datetime | None
    completed_at: datetime | None


class QueueEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    position: int | None
    scheduled_at: datetime
    checked_in_at: datetime | None
    consult_started_at: datetime | None
    from_earlier_day: bool  # left open from an earlier day: shown apart, never hidden
    triage_level: str | None  # emergency, urgent or standard; None until triaged
    red_flags: list[str]  # danger-sign codes; empty for staff without clinical access


class DayEntryResponse(BaseModel):
    """One visit on a branch's day list. The patient's name, and nothing else about them."""

    model_config = ConfigDict(from_attributes=True)

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    starts_at: datetime
    ends_at: datetime
    checked_in_at: datetime | None


class RecordTriage(BaseModel):
    """Codes only. Any danger sign makes the level emergency, whatever is sent."""

    id: uuid.UUID | None = None  # made by the device, so a re-send records nothing new
    level: str = Field(max_length=20)
    red_flags: list[str] = Field(default_factory=list, max_length=20)


class TriageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    level: str
    red_flags: list[str]
    recorded_by_id: uuid.UUID
    recorded_at: datetime


class PublishHours(BaseModel):
    """Weekly hours for the person sending them. Times are Lagos clock times, e.g. 09:00."""

    id: uuid.UUID | None = None
    branch_id: uuid.UUID
    weekday: int = Field(ge=0, le=6)  # 0 Monday ... 6 Sunday
    starts: time
    ends: time
    visit_type: str = Field(default="in_person", max_length=20)
    slot_minutes: int = 15


class HoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinician_id: uuid.UUID
    branch_id: uuid.UUID
    weekday: int
    starts: time
    ends: time
    visit_type: str
    slot_minutes: int


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    starts_at: datetime
    ends_at: datetime
    branch_id: uuid.UUID
    visit_type: str
