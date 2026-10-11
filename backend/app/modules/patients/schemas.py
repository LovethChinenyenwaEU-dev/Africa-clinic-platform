import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    """The form for registering a patient. There is no clinic box: it comes from the guard."""

    full_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date
    sex: str = Field(min_length=1, max_length=20)
    phone: str | None = Field(default=None, max_length=40)
    confirmed_not_duplicate: bool = False


class PatientResponse(BaseModel):
    """What we say about a patient. No clinic ID and no staff ID leave the building."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    date_of_birth: date
    sex: str
    phone: str | None