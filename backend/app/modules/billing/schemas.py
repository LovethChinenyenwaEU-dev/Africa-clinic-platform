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
    """An invoice without its lines, for lists, with what is paid and still owed."""

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
    paid_kobo: int = 0
    balance_kobo: int = 0
    payment_status: str = "not_issued"  # not_issued, unpaid, part_paid or paid


class RecordPayment(BaseModel):
    """Money received. Cash, or a bank transfer with the bank's reference."""

    id: uuid.UUID | None = None
    method: str = Field(max_length=20)
    amount_kobo: StrictInt
    reference: str | None = Field(default=None, max_length=100)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    method: str
    amount_kobo: int
    reference: str | None
    receipt_number: str
    received_by_id: uuid.UUID
    received_at: datetime


class InvoiceResponse(InvoiceSummaryResponse):
    lines: list[InvoiceLineResponse]
    payments: list[PaymentResponse]


class ReceiptResponse(BaseModel):
    """Everything a printed receipt shows."""

    payment: PaymentResponse
    clinic_name: str
    patient_name: str
    invoice_number: str
    invoice_total_kobo: int
    paid_to_date_kobo: int
    balance_after_kobo: int
    received_by_name: str
    check_code: str
