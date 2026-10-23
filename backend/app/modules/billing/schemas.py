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


class StartInvoice(BaseModel):
    """Start the invoice for a visit."""

    id: uuid.UUID | None = None
    appointment_id: uuid.UUID


class AddInvoiceLine(BaseModel):
    """A service from the price list, and how many."""

    id: uuid.UUID | None = None
    price_item_id: uuid.UUID
    quantity: StrictInt = 1


class VoidInvoice(BaseModel):
    reason: str = Field(max_length=400)


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    price_item_id: uuid.UUID
    description: str
    unit_price_kobo: int
    quantity: int
    amount_kobo: int
    added_at: datetime


class InvoiceSummaryResponse(BaseModel):
    """An invoice without its lines, for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID
    status: str
    number: str | None
    total_kobo: int
    created_at: datetime
    issued_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None


class InvoiceResponse(InvoiceSummaryResponse):
    lines: list[InvoiceLineResponse]
