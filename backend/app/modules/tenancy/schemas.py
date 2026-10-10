import uuid

from pydantic import BaseModel, ConfigDict


class BranchResponse(BaseModel):
    """What we say about a branch."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str