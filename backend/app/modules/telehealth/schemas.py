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
