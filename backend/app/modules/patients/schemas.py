import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PatientCreate(BaseModel):
    """The form for registering a patient. There is no clinic box: it comes from the guard."""

    id: uuid.UUID | None = None  # made by the device, so a re-sent form creates nothing new
    full_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date
    sex: str = Field(min_length=1, max_length=20)
    phone: str | None = Field(default=None, max_length=40)
    confirmed_not_duplicate: bool = False
    # Filled in with no network: a possible duplicate is flagged for review, not refused.
    registered_offline: bool = False


class PatientResponse(BaseModel):
    """What we say about a patient. No clinic ID and no staff ID leave the building."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    date_of_birth: date
    sex: str
    phone: str | None
    review_status: str | None = None
    duplicate_of_id: uuid.UUID | None = None


class ReviewMatch(BaseModel):
    patient: PatientResponse
    reason: str  # same_phone or same_name_and_birth_date


class ReviewItemResponse(BaseModel):
    patient: PatientResponse
    matches: list[ReviewMatch]


class ReviewDecision(BaseModel):
    """`new_person`, or `duplicate` of the patient in `duplicate_of`."""

    decision: Literal["new_person", "duplicate"]
    duplicate_of: uuid.UUID | None = None

    @model_validator(mode="after")
    def duplicate_names_the_original(self):
        if (self.decision == "duplicate") != (self.duplicate_of is not None):
            raise ValueError("Give duplicate_of only, and always, when the decision is duplicate.")
        return self
