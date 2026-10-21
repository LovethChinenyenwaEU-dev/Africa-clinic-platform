import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class StartSignIn(BaseModel):
    clinic_id: uuid.UUID
    phone: str = Field(max_length=40)
    date_of_birth: date


class StartSignInAnswer(BaseModel):
    """The same answer whether or not anyone matched."""

    message: str
    development_code: str | None = None  # development only: SMS is switched off there


class FinishSignIn(StartSignIn):
    code: str = Field(min_length=4, max_length=10)


class PatientToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Me(BaseModel):
    """The patient's own name, to greet them. Nothing else is needed on the page."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str


class MyVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    visit_type: str
    status: str
    clinician_name: str | None


class MySummaryResponse(BaseModel):
    """An approved summary, as the patient reads it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    approved_at: datetime | None


class RemoteCareConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consented: bool
    wording: str | None  # the clinic's current wording, to read before agreeing
    version: int | None


class RemoteSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinician_id: uuid.UUID
    clinician_name: str
    starts_at: datetime
    ends_at: datetime


class BookRemoteVisit(BaseModel):
    id: uuid.UUID | None = None  # made by the device, so a booking sent twice is made once
    clinician_id: uuid.UUID
    starts_at: datetime


class PatientIntake(BaseModel):
    id: uuid.UUID | None = None
    reason: str = Field(max_length=1000)
    red_flags: list[str] = Field(default_factory=list, max_length=20)


class PatientIntakeAnswer(BaseModel):
    outcome: str  # ready or escalated
    advice: str | None = None  # what to do now, when a danger sign was reported


class PatientRoom(BaseModel):
    mode: str  # video, audio or text
    video_url: str | None
    audio_url: str | None


class PatientMessage(BaseModel):
    id: uuid.UUID | None = None
    body: str = Field(max_length=4000)


class ChatMessage(BaseModel):
    """A chat line as the patient sees it: who wrote it is "you" or "the clinician"."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: str  # patient or staff
    body: str
    sent_at: datetime
