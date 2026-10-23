import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class AddPrice(BaseModel):
    """A new service. The price is in kobo: 500000 is 5,000 naira."""

    id: uuid.UUID | None = None  # sent by the screen, so a repeated send adds it once
    name: str = Field(max_length=200)
    code: str | None = Field(default=None, max_length=40)
    price_kobo: StrictInt


class ChangePrice(BaseModel):
    """The whole service as it should be now. active False retires it."""

    name: str = Field(max_length=200)
    code: str | None = Field(default=None, max_length=40)
    price_kobo: StrictInt
    active: bool


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str | None
    price_kobo: int
    active: bool
    created_at: datetime
    updated_at: datetime | None
