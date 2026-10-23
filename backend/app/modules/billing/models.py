import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class PriceItem(SQLModel, table=True):
    """One service the clinic charges for, with its price in kobo (100 kobo = 1 naira).

    Never deleted: a service no longer offered is retired (active = False), so old
    invoices can still say what was charged. Invoices copy the name and price when
    they are written, so changing a price never changes an invoice already issued.
    No two active services of one clinic share a name (a unique index in the migration).
    """

    __tablename__ = "price_item"
    __table_args__ = (CheckConstraint("price_kobo >= 0", name="ck_price_item_price"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    name: str
    code: str | None = None  # the clinic's own short code, e.g. "CONS-GP"
    price_kobo: int = Field(sa_column=Column(BigInteger, nullable=False))
    active: bool = True
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class InvoiceStatus(StrEnum):
    DRAFT = "draft"  # lines can still be added and removed
    ISSUED = "issued"  # numbered and frozen: changed only by payments and refunds
    VOID = "void"  # a draft made by mistake, cancelled before it was issued


class Invoice(SQLModel, table=True):
    """What a patient owes for one visit. Personal data: who was seen and what for.

    One invoice per visit at a time (a unique index in the migration ignores void ones).
    The number is given when the invoice is issued, in order, per clinic.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_invoice_tenant_number"),
        CheckConstraint("status IN ('draft', 'issued', 'void')", name="ck_invoice_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id", index=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id")
    status: str = InvoiceStatus.DRAFT.value
    number: str | None = None  # "INV-000042", once issued
    total_kobo: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    issued_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    issued_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    voided_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    voided_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    void_reason: str | None = None


class InvoiceLine(SQLModel, table=True):
    """One service on an invoice. The name and price are copied from the price list when
    the line is added, so a later price change never changes this line."""

    __tablename__ = "invoice_line"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 100", name="ck_invoice_line_quantity"),
        CheckConstraint("unit_price_kobo >= 0", name="ck_invoice_line_price"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    invoice_id: uuid.UUID = Field(foreign_key="invoice.id", index=True)
    price_item_id: uuid.UUID = Field(foreign_key="price_item.id")
    description: str
    unit_price_kobo: int = Field(sa_column=Column(BigInteger, nullable=False))
    quantity: int = 1
    amount_kobo: int = Field(sa_column=Column(BigInteger, nullable=False))
    added_by_id: uuid.UUID = Field(foreign_key="staff.id")
    added_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class InvoiceCounter(SQLModel, table=True):
    """The last invoice number each clinic gave. Locked while a number is taken, so two
    invoices issued at the same moment never get the same number."""

    __tablename__ = "invoice_counter"

    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", primary_key=True)
    last_number: int = 0


class PaymentMethod(StrEnum):
    CASH = "cash"
    TRANSFER = "transfer"  # a bank transfer the clinic has seen arrive


class Payment(SQLModel, table=True):
    """Money received against an issued invoice. Never edited or deleted: a mistake is
    put right by a refund (Step 4), so the record of what happened stays.

    Each payment gets the clinic's next receipt number. A bank transfer must carry its
    reference, and one transfer reference is recorded once per clinic (a unique index in
    the migration), so the same transfer cannot be counted twice.
    """

    __table_args__ = (
        UniqueConstraint("tenant_id", "receipt_number", name="uq_payment_tenant_receipt"),
        CheckConstraint("amount_kobo > 0", name="ck_payment_amount"),
        CheckConstraint("method IN ('cash', 'transfer')", name="ck_payment_method"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    invoice_id: uuid.UUID = Field(foreign_key="invoice.id", index=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    method: str
    amount_kobo: int = Field(sa_column=Column(BigInteger, nullable=False))
    reference: str | None = None  # the bank's transfer reference; optional for cash
    receipt_number: str  # "RCT-000042"
    received_by_id: uuid.UUID = Field(foreign_key="staff.id")
    received_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class ReceiptCounter(SQLModel, table=True):
    """The last receipt number each clinic gave, locked while a number is taken."""

    __tablename__ = "receipt_counter"

    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", primary_key=True)
    last_number: int = 0
