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
