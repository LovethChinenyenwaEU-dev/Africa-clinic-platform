import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntakeForm(BaseModel):
    id: uuid.UUID | None = None  # made by the device, so a re-send records nothing new
    reason: str = Field(max_length=1000)  # the patient's words; the service allows 500
    red_flags: list[str] = Field(default_factory=list, max_length=20)


class IntakeResponse(BaseModel):
    """What the person taking the intake needs back. `advice` is set when escalated."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    outcome: str  # ready or escalated
    red_flags: list[str]
    recorded_at: datetime
    advice: str | None = None


class IntakeRecord(IntakeResponse):
    """The full intake, for clinicians: the reason is health information."""

    reason: str
    source: str
    recorded_by_id: uuid.UUID | None


class TeleconsultStatus(BaseModel):
    """For booking screens: no clinical text."""

    consented: bool
    intake: str | None  # ready, escalated, or None (not taken yet)


class RoomResponse(BaseModel):
    """The room of a remote visit. Links only: the call itself runs at the provider."""

    appointment_id: uuid.UUID
    provider: str
    mode: str  # video, audio or text
    video_url: str | None
    audio_url: str | None


class ChangeMode(BaseModel):
    mode: str = Field(max_length=10)  # video, audio or text
    reason: str = Field(max_length=30)  # poor_connection, patient_choice or clinician_choice


class SendMessage(BaseModel):
    id: uuid.UUID | None = None  # made by the device, so a re-sent message appears once
    body: str = Field(max_length=4000)  # the service allows 2000 after trimming


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: str  # staff or patient
    sender_staff_id: uuid.UUID | None
    body: str
    sent_at: datetime


class ModeChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_mode: str
    to_mode: str
    reason: str
    changed_at: datetime
