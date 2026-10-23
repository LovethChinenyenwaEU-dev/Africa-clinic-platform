"""Payments and receipts (Week 10 Step 3, FR-B2).

Front desk or billing records money received against an issued invoice: cash, or a
bank transfer they have seen arrive (with the bank's reference). Paystack comes in
Step 5. Each payment gets the clinic's next receipt number. A payment is never edited
or deleted; a mistake is put right by a refund (Step 4).

Nobody can take more than is still owed: the invoice is locked while the balance is
worked out, so two people taking money at once cannot both be paid in full.
A receipt carries a short check code made with the server's secret, so a printed
receipt can later be checked as one the clinic really gave.
"""
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col

from app.core.config import settings
from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.billing.invoices import locked_invoice, take_number, view_lines
from app.modules.billing.models import InvoiceStatus, Payment, PaymentMethod, ReceiptCounter
from app.modules.billing.money import naira
from app.modules.identity.service import get_staff_in_tenant
from app.modules.patients.service import patient_names
from app.modules.tenancy.service import clinic_name

MIN_REFERENCE_LENGTH = 3
MAX_REFERENCE_LENGTH = 60


class InvalidPaymentError(ValueError):
    """The amount, method or reference is not acceptable, or more than is owed."""


class PaymentNotAllowedError(Exception):
    """This invoice cannot take money now: not issued, void, or already paid."""


class DuplicateTransferError(Exception):
    """This bank transfer reference is already recorded in this clinic."""


class PaymentNotFoundError(Exception):
    """No such payment in this clinic."""


@dataclass(frozen=True)
class Receipt:
    payment: Payment
    clinic_name: str
    patient_name: str
    invoice_number: str
    invoice_total_kobo: int
    paid_to_date_kobo: int  # this payment and every one before it
    balance_after_kobo: int
    received_by_name: str
    check_code: str


def _method(value: str) -> str:
    try:
        return PaymentMethod(value).value
    except ValueError:
        raise InvalidPaymentError("The method must be cash or transfer.") from None


def _reference(method: str, reference: str | None) -> str | None:
    text = " ".join((reference or "").split()) or None
    if method == PaymentMethod.TRANSFER.value and text is None:
        raise InvalidPaymentError("A transfer needs the bank's reference.")
    if text is not None and not MIN_REFERENCE_LENGTH <= len(text) <= MAX_REFERENCE_LENGTH:
        raise InvalidPaymentError(
            f"The reference must be {MIN_REFERENCE_LENGTH} to {MAX_REFERENCE_LENGTH} characters."
        )
    return text


def _transfer_seen(session: Session, *, tenant_id: uuid.UUID, reference: str) -> bool:
    statement = (
        tenant_select(Payment, tenant_id)
        .where(col(Payment.method) == PaymentMethod.TRANSFER.value)
        .where(func.lower(col(Payment.reference)) == reference.lower())
    )
    return session.exec(statement).first() is not None


def record_payment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    method: str,
    amount_kobo: int,
    reference: str | None = None,
    payment_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Payment:
    """Record money received. Sending the same payment ID twice records it once."""
    if payment_id is not None:
        existing = get_in_tenant(session, Payment, tenant_id=tenant_id, row_id=payment_id)
        if isinstance(existing, Payment):
            return existing
    kind = _method(method)
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, int) or amount_kobo <= 0:
        raise InvalidPaymentError("The amount must be a whole number of kobo, above zero.")
    clean_reference = _reference(kind, reference)

    invoice = locked_invoice(session, tenant_id=tenant_id, invoice_id=invoice_id)
    if invoice.status != InvoiceStatus.ISSUED.value:
        session.rollback()
        raise PaymentNotAllowedError("Issue the invoice before taking payment.")
    owed = view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id).balance_kobo
    if owed <= 0:
        session.rollback()
        raise PaymentNotAllowedError("This invoice is already paid.")
    if amount_kobo > owed:
        session.rollback()
        raise InvalidPaymentError(f"That is more than the {naira(owed)} still owed.")
    if kind == PaymentMethod.TRANSFER.value and _transfer_seen(
        session, tenant_id=tenant_id, reference=clean_reference or ""
    ):
        session.rollback()
        raise DuplicateTransferError("This transfer reference is already recorded.")

    payment = Payment(
        id=payment_id or uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        patient_id=invoice.patient_id,
        method=kind,
        amount_kobo=amount_kobo,
        reference=clean_reference,
        receipt_number=take_number(
            session, counter=ReceiptCounter, tenant_id=tenant_id, prefix="RCT"
        ),
        received_by_id=actor_id,
        received_at=now or datetime.now(UTC),
    )
    session.add(payment)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PAYMENT_RECORD,
        patient_id=invoice.patient_id,
        entity_id=payment.id,
    )
    try:
        session.commit()
    except IntegrityError:
        # The same transfer recorded by someone else at the same moment.
        session.rollback()
        raise DuplicateTransferError("This transfer reference is already recorded.") from None
    session.refresh(payment)
    return payment


def check_code(payment: Payment) -> str:
    """Ten characters only this server can make for this payment."""
    message = (
        f"{payment.tenant_id}:{payment.receipt_number}:{payment.amount_kobo}:"
        f"{payment.received_at.astimezone(UTC).isoformat()}"
    )
    digest = hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256)
    return digest.hexdigest()[:10].upper()


def view_receipt(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, payment_id: uuid.UUID
) -> Receipt:
    """Everything a printed receipt shows. Written in the diary: it names the patient."""
    payment = get_in_tenant(session, Payment, tenant_id=tenant_id, row_id=payment_id)
    if not isinstance(payment, Payment):
        raise PaymentNotFoundError("Payment not found.")
    invoice_view = view_lines(session, tenant_id=tenant_id, invoice_id=payment.invoice_id)
    so_far = [
        earlier
        for earlier in invoice_view.payments
        if (earlier.received_at, earlier.receipt_number)
        <= (payment.received_at, payment.receipt_number)
    ]
    paid_to_date = sum(earlier.amount_kobo for earlier in so_far)
    receiver = get_staff_in_tenant(session, tenant_id=tenant_id, staff_id=payment.received_by_id)
    names = patient_names(session, tenant_id=tenant_id, patient_ids=[payment.patient_id])

    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.RECEIPT_VIEW,
        patient_id=payment.patient_id,
        entity_id=payment.id,
    )
    session.commit()
    session.refresh(payment)
    return Receipt(
        payment=payment,
        clinic_name=clinic_name(session, tenant_id=tenant_id),
        patient_name=names.get(payment.patient_id, ""),
        invoice_number=invoice_view.invoice.number or "",
        invoice_total_kobo=invoice_view.invoice.total_kobo,
        paid_to_date_kobo=paid_to_date,
        balance_after_kobo=invoice_view.invoice.total_kobo - paid_to_date,
        received_by_name=receiver.full_name if receiver else "",
        check_code=check_code(payment),
    )
