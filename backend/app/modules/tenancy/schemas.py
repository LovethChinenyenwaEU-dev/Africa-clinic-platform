import uuid

from pydantic import BaseModel, ConfigDict, Field


class BranchResponse(BaseModel):
    """What we say about a branch."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str


class BranchCreate(BaseModel):
    """The form an admin fills in to add a branch."""

    name: str = Field(min_length=1, max_length=120)
    city: str = Field(default="", max_length=120)