import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """The form a person fills in to log in."""

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """The answer we send back: the wristband."""

    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    """What we are willing to say about the logged-in person. No password_hash, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    role: str
class StaffCreate(BaseModel):
    """The form an admin fills in to add a staff member. No clinic box: it comes from the guard."""

    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class StaffResponse(BaseModel):
    """What we say about a staff member. No password_hash, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool