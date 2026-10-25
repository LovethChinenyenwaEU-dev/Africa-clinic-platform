import uuid
from datetime import date, datetime

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
    refunded_kobo: int = 0  # approved refunds only
    balance_kobo: int = 0
    credit_kobo: int = 0  # paid beyond the total, to be given back
    # not_issued, unpaid, part_paid, paid, overpaid or refunded
    payment_status: str = "not_issued"


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


class RequestRefund(BaseModel):
    """Money back from one payment: how much, how it goes back, and why."""

    id: uuid.UUID | None = None
    amount_kobo: StrictInt
    method: str = Field(max_length=20)
    reason: str = Field(max_length=400)


class DecideRefund(BaseModel):
    """The admin's note. Needed to reject; optional to approve."""

    note: str | None = Field(default=None, max_length=400)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    payment_id: uuid.UUID
    patient_id: uuid.UUID
    amount_kobo: int
    method: str
    reason: str
    status: str
    refund_number: str | None
    requested_by_id: uuid.UUID
    requested_at: datetime
    decided_by_id: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None


class StartOnlinePayment(BaseModel):
    """A payment link. No amount: everything still owed. No email: the clinic's fallback."""

    id: uuid.UUID | None = None
    amount_kobo: StrictInt | None = None
    email: str | None = Field(default=None, max_length=200)


class OnlinePaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    gateway: str
    reference: str
    amount_kobo: int
    link: str
    status: str
    failure_reason: str | None
    payment_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None


class InvoiceResponse(InvoiceSummaryResponse):
    lines: list[InvoiceLineResponse]
    payments: list[PaymentResponse]
    refunds: list[RefundResponse]
    online_payments: list[OnlinePaymentResponse]


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


class MethodTotalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: str
    count: int
    amount_kobo: int


class StaffTotalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    staff_id: uuid.UUID
    name: str
    payments: int
    taken_kobo: int


class FlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    message: str
    invoice_number: str | None
    amount_kobo: int | None


class TakingsResponse(BaseModel):
    """One Lagos day's money. Net cash is what should be in the drawer."""

    model_config = ConfigDict(from_attributes=True)

    day: date
    money_in: list[MethodTotalResponse]
    money_out: list[MethodTotalResponse]
    net_by_method: list[MethodTotalResponse]
    total_in_kobo: int
    total_out_kobo: int
    net_kobo: int
    by_staff: list[StaffTotalResponse]
    invoices_issued: int
    billed_kobo: int
    flags: list[FlagResponse]


class TakingsExportResponse(BaseModel):
    """The CSV inside JSON: the staff pass-through only carries JSON."""

    filename: str
    csv: str
