"""Invoices: what a patient owes for one visit (Week 10 Step 2, FR-B1).

Front desk or billing starts the invoice for a visit and adds services from the
price list. Each line copies the service's name and price at that moment. While
it is a draft, lines can be added and removed, or the draft voided with a reason.
Issuing gives it the clinic's next number and freezes it: from then on only
payments and refunds (Steps 3 and 4) touch it.

An invoice says who was seen and what for, so every view is in the audit log.
"""
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.billing.models import (
    Invoice,
    InvoiceCounter,
    InvoiceLine,
    InvoiceStatus,
    OnlinePayment,
    Payment,
    PriceItem,
    ReceiptCounter,
    Refund,
    RefundCounter,
    RefundStatus,
)
from app.modules.patients.service import patient_exists
from app.modules.scheduling.service import get_appointment
from app.modules.scheduling.statuses import AppointmentStatus

MAX_QUANTITY = 100
MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 300


class InvalidInvoiceError(ValueError):
    """The request does not make sense (no lines, a retired service, a bad quantity)."""


class InvoiceNotFoundError(Exception):
    """No such invoice, line, visit or service in this clinic."""


class InvoiceLockedError(Exception):
    """The invoice is issued or void: it can no longer be changed."""


class PaymentStatus(StrEnum):
    """How much of an issued invoice is paid. Worked out from the payments, never stored,
    so it can never disagree with them."""

    NOT_ISSUED = "not_issued"  # a draft or a void: nothing is owed yet
    UNPAID = "unpaid"
    PART_PAID = "part_paid"
    PAID = "paid"
    REFUNDED = "refunded"  # everything paid was given back
    # More came in than was owed, e.g. a payment link paid after cash settled the bill.
    # Someone must give the difference back (a refund); the daily takings show it.
    OVERPAID = "overpaid"


@dataclass(frozen=True)
class InvoiceView:
    invoice: Invoice
    lines: list[InvoiceLine]
    payments: list[Payment] = field(default_factory=list)
    refunds: list[Refund] = field(default_factory=list)  # asked, approved and rejected
    online_payments: list[OnlinePayment] = field(default_factory=list)  # payment links

    @property
    def paid_kobo(self) -> int:
        """Everything received, before refunds."""
        return sum(payment.amount_kobo for payment in self.payments)

    @property
    def refunded_kobo(self) -> int:
        """Approved refunds only: a request still waiting has given nothing back."""
        return sum(
            refund.amount_kobo
            for refund in self.refunds
            if refund.status == RefundStatus.APPROVED.value
        )

    @property
    def balance_kobo(self) -> int:
        """Still owed. Zero for a draft or a void. A refund is for something not given,
        so it lowers what was paid and what is owed alike: the balance does not change."""
        if self.invoice.status != InvoiceStatus.ISSUED.value:
            return 0
        return max(0, self.invoice.total_kobo - self.paid_kobo)

    @property
    def credit_kobo(self) -> int:
        """Paid beyond the total and not yet given back: the clinic owes the patient this."""
        if self.invoice.status != InvoiceStatus.ISSUED.value:
            return 0
        return max(0, self.paid_kobo - self.refunded_kobo - self.invoice.total_kobo)

    @property
    def payment_status(self) -> PaymentStatus:
        if self.invoice.status != InvoiceStatus.ISSUED.value:
            return PaymentStatus.NOT_ISSUED
        if self.paid_kobo and self.refunded_kobo >= self.paid_kobo:
            return PaymentStatus.REFUNDED
        if self.credit_kobo > 0:
            return PaymentStatus.OVERPAID
        if self.balance_kobo <= 0:
            return PaymentStatus.PAID
        return PaymentStatus.PART_PAID if self.paid_kobo else PaymentStatus.UNPAID


def _invoice(
    session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID, lock: bool = False
) -> Invoice:
    statement = tenant_select(Invoice, tenant_id).where(col(Invoice.id) == invoice_id)
    if lock:
        # Two people pressing "issue" at once: the second waits, then sees it issued.
        statement = statement.with_for_update()
    row = session.exec(statement).first()
    if row is None:
        raise InvoiceNotFoundError("Invoice not found.")
    return row


def locked_invoice(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    """The invoice, locked until the caller commits: for taking money against it."""
    return _invoice(session, tenant_id=tenant_id, invoice_id=invoice_id, lock=True)


def _draft(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = _invoice(session, tenant_id=tenant_id, invoice_id=invoice_id, lock=True)
    if invoice.status != InvoiceStatus.DRAFT.value:
        session.rollback()  # let go of the lock before saying no
        raise InvoiceLockedError(f"This invoice is {invoice.status}: it can no longer change.")
    return invoice


def _lines(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> list[InvoiceLine]:
    statement = (
        tenant_select(InvoiceLine, tenant_id)
        .where(col(InvoiceLine.invoice_id) == invoice_id)
        .order_by(col(InvoiceLine.added_at), col(InvoiceLine.id))
    )
    return list(session.exec(statement).all())


def _live_invoice_for_visit(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> Invoice | None:
    statement = (
        tenant_select(Invoice, tenant_id)
        .where(col(Invoice.appointment_id) == appointment_id)
        .where(col(Invoice.status) != InvoiceStatus.VOID.value)
    )
    return session.exec(statement).first()


def _audit(
    session: Session, invoice: Invoice, *, actor_id: uuid.UUID, action: AuditAction
) -> None:
    add_audit_event(
        session,
        tenant_id=invoice.tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=invoice.patient_id,
        entity_id=invoice.id,
    )


def start_invoice(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    invoice_id: uuid.UUID | None = None,
) -> Invoice:
    """Start the invoice for a visit. If the visit already has one, that one is returned:
    a visit is billed once (void a draft to start again)."""
    if invoice_id is not None:
        existing = get_in_tenant(session, Invoice, tenant_id=tenant_id, row_id=invoice_id)
        if isinstance(existing, Invoice):
            return existing
    visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit is None:
        raise InvoiceNotFoundError("Visit not found.")
    if visit.status == AppointmentStatus.CANCELLED.value:
        raise InvalidInvoiceError("A cancelled visit is not billed.")
    current = _live_invoice_for_visit(session, tenant_id=tenant_id, appointment_id=visit.id)
    if current is not None:
        return current

    invoice = Invoice(
        id=invoice_id or uuid.uuid4(),
        tenant_id=tenant_id,
        patient_id=visit.patient_id,
        appointment_id=visit.id,
        created_by_id=actor_id,
    )
    session.add(invoice)
    _audit(session, invoice, actor_id=actor_id, action=AuditAction.INVOICE_CREATE)
    try:
        session.commit()
    except IntegrityError:
        # Someone else started this visit's invoice at the same moment: use theirs.
        session.rollback()
        current = _live_invoice_for_visit(session, tenant_id=tenant_id, appointment_id=visit.id)
        if current is None:
            raise
        return current
    session.refresh(invoice)
    return invoice


def add_line(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    price_item_id: uuid.UUID,
    quantity: int = 1,
    line_id: uuid.UUID | None = None,
) -> InvoiceView:
    """Add a service from the price list to a draft. The name and price are copied now."""
    if line_id is not None:
        existing = get_in_tenant(session, InvoiceLine, tenant_id=tenant_id, row_id=line_id)
        if isinstance(existing, InvoiceLine) and existing.invoice_id == invoice_id:
            return view_lines(session, tenant_id=tenant_id, invoice_id=invoice_id)
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise InvalidInvoiceError("The quantity must be a whole number.")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise InvalidInvoiceError(f"The quantity must be between 1 and {MAX_QUANTITY}.")
    invoice = _draft(session, tenant_id=tenant_id, invoice_id=invoice_id)
    service = get_in_tenant(session, PriceItem, tenant_id=tenant_id, row_id=price_item_id)
    if not isinstance(service, PriceItem):
        raise InvoiceNotFoundError("Service not found.")
    if not service.active:
        raise InvalidInvoiceError("This service is retired; choose a current one.")

    line = InvoiceLine(
        id=line_id or uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        price_item_id=service.id,
        description=service.name,
        unit_price_kobo=service.price_kobo,
        quantity=quantity,
        amount_kobo=service.price_kobo * quantity,
        added_by_id=actor_id,
    )
    invoice.total_kobo += line.amount_kobo
    session.add(line)
    session.add(invoice)
    _audit(session, invoice, actor_id=actor_id, action=AuditAction.INVOICE_LINE_ADD)
    session.commit()
    return view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id)


def remove_line(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
) -> InvoiceView:
    """Take a line off a draft."""
    invoice = _draft(session, tenant_id=tenant_id, invoice_id=invoice_id)
    line = get_in_tenant(session, InvoiceLine, tenant_id=tenant_id, row_id=line_id)
    if not isinstance(line, InvoiceLine) or line.invoice_id != invoice.id:
        raise InvoiceNotFoundError("Line not found.")
    invoice.total_kobo -= line.amount_kobo
    session.delete(line)
    session.add(invoice)
    _audit(session, invoice, actor_id=actor_id, action=AuditAction.INVOICE_LINE_REMOVE)
    session.commit()
    return view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id)


def take_number(
    session: Session,
    *,
    counter: type[InvoiceCounter] | type[ReceiptCounter] | type[RefundCounter],
    tenant_id: uuid.UUID,
    prefix: str,
) -> str:
    """The clinic's next number from a counter ("INV-000042", "RCT-000007"). The counter
    row stays locked until the caller commits, so two at the same moment never share one."""
    session.execute(
        pg_insert(counter)
        .values(tenant_id=tenant_id, last_number=0)
        .on_conflict_do_nothing(index_elements=["tenant_id"])
    )
    row = session.exec(
        select(counter).where(col(counter.tenant_id) == tenant_id).with_for_update()
    ).one()
    row.last_number += 1
    session.add(row)
    return f"{prefix}-{row.last_number:06d}"


def issue_invoice(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    now: datetime | None = None,
) -> InvoiceView:
    """Number and freeze the invoice. Issuing it again changes nothing."""
    invoice = _invoice(session, tenant_id=tenant_id, invoice_id=invoice_id, lock=True)
    if invoice.status == InvoiceStatus.ISSUED.value:
        session.rollback()  # let go of the lock
        return view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id)
    if invoice.status != InvoiceStatus.DRAFT.value:
        session.rollback()
        raise InvoiceLockedError(f"This invoice is {invoice.status}: it can no longer change.")
    lines = _lines(session, tenant_id=tenant_id, invoice_id=invoice.id)
    if not lines:
        session.rollback()
        raise InvalidInvoiceError("Add at least one service before issuing the invoice.")

    invoice.total_kobo = sum(line.amount_kobo for line in lines)  # the lines have the last word
    invoice.number = take_number(
        session, counter=InvoiceCounter, tenant_id=tenant_id, prefix="INV"
    )
    invoice.status = InvoiceStatus.ISSUED.value
    invoice.issued_by_id = actor_id
    invoice.issued_at = now or datetime.now(UTC)
    session.add(invoice)
    _audit(session, invoice, actor_id=actor_id, action=AuditAction.INVOICE_ISSUE)
    session.commit()
    return view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id)


def void_invoice(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> InvoiceView:
    """Cancel a draft made by mistake. An issued invoice is never voided: a refund
    (Step 4) undoes money, and the record of what was billed stays."""
    clean_reason = " ".join(reason.split())
    if not MIN_REASON_LENGTH <= len(clean_reason) <= MAX_REASON_LENGTH:
        raise InvalidInvoiceError(
            f"Say why, in {MIN_REASON_LENGTH} to {MAX_REASON_LENGTH} characters."
        )
    invoice = _draft(session, tenant_id=tenant_id, invoice_id=invoice_id)
    invoice.status = InvoiceStatus.VOID.value
    invoice.void_reason = clean_reason
    invoice.voided_by_id = actor_id
    invoice.voided_at = now or datetime.now(UTC)
    session.add(invoice)
    _audit(session, invoice, actor_id=actor_id, action=AuditAction.INVOICE_VOID)
    session.commit()
    return view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id)


def _payments(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> list[Payment]:
    statement = (
        tenant_select(Payment, tenant_id)
        .where(col(Payment.invoice_id) == invoice_id)
        .order_by(col(Payment.received_at), col(Payment.receipt_number))
    )
    return list(session.exec(statement).all())


def _refunds(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> list[Refund]:
    statement = (
        tenant_select(Refund, tenant_id)
        .where(col(Refund.invoice_id) == invoice_id)
        .order_by(col(Refund.requested_at), col(Refund.id))
    )
    return list(session.exec(statement).all())


def _online(
    session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[OnlinePayment]:
    statement = (
        tenant_select(OnlinePayment, tenant_id)
        .where(col(OnlinePayment.invoice_id) == invoice_id)
        .order_by(col(OnlinePayment.created_at), col(OnlinePayment.id))
    )
    return list(session.exec(statement).all())


def view_lines(session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> InvoiceView:
    """The invoice, its lines and its payments, with no diary line: for answers to a
    change the person just made (that change is already in the diary)."""
    invoice = _invoice(session, tenant_id=tenant_id, invoice_id=invoice_id)
    session.refresh(invoice)
    return InvoiceView(
        invoice,
        _lines(session, tenant_id=tenant_id, invoice_id=invoice.id),
        _payments(session, tenant_id=tenant_id, invoice_id=invoice.id),
        _refunds(session, tenant_id=tenant_id, invoice_id=invoice.id),
        _online(session, tenant_id=tenant_id, invoice_id=invoice.id),
    )


def view_invoice(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID
) -> InvoiceView:
    """Open an invoice. Written in the diary: it shows who was seen and what for."""
    result = view_lines(session, tenant_id=tenant_id, invoice_id=invoice_id)
    _audit(session, result.invoice, actor_id=actor_id, action=AuditAction.INVOICE_VIEW)
    session.commit()
    return result


def view_visit_invoice(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, appointment_id: uuid.UUID
) -> InvoiceView:
    """The live (not void) invoice of a visit."""
    invoice = _live_invoice_for_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if invoice is None:
        raise InvoiceNotFoundError("This visit has no invoice yet.")
    return view_invoice(session, tenant_id=tenant_id, actor_id=actor_id, invoice_id=invoice.id)


def list_patient_invoices(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, patient_id: uuid.UUID
) -> list[InvoiceView]:
    """A patient's invoices, newest first, voided drafts included (they say why),
    each with what is paid and still owed."""
    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise InvoiceNotFoundError("Patient not found.")
    statement = (
        tenant_select(Invoice, tenant_id)
        .where(col(Invoice.patient_id) == patient_id)
        .order_by(col(Invoice.created_at).desc(), col(Invoice.id))
    )
    rows = [
        InvoiceView(
            invoice,
            _lines(session, tenant_id=tenant_id, invoice_id=invoice.id),
            _payments(session, tenant_id=tenant_id, invoice_id=invoice.id),
            _refunds(session, tenant_id=tenant_id, invoice_id=invoice.id),
            _online(session, tenant_id=tenant_id, invoice_id=invoice.id),
        )
        for invoice in session.exec(statement).all()
    ]
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.INVOICE_LIST,
        patient_id=patient_id,
    )
    session.commit()
    return rows
