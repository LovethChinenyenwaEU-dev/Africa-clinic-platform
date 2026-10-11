import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsentTextCreate(BaseModel):
    """The form an admin fills in to publish new wording."""

    purpose: str = Field(min_length=1, max_length=40)
    body: str = Field(min_length=1, max_length=5000)


class ConsentTextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: str
    version: int
    body: str
    created_at: datetime


class ConsentCreate(BaseModel):
    """The form for recording that a patient agreed. No clinic box and no patient box: both
    come from the guard and the address."""

    purpose: str = Field(min_length=1, max_length=40)
    granted_by: str = Field(min_length=1, max_length=20)


class ConsentResponse(BaseModel):
    """What we say about a consent. Staff IDs and clinic IDs stay inside."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    purpose: str
    wording_version: int
    granted_by: str
    granted_at: datetime
    revoked_at: datetime | None