"""Online payment through the gateway (Week 10 Step 5, FR-B2, FR-B4).

1. Front desk or billing makes a payment link for an issued invoice (by default for
   everything still owed). The patient pays on the gateway's page.
2. The gateway tells us by a signed webhook. A webhook is only a hint: we ask the
   gateway (verify) what really happened before any money is counted.
3. Staff can press "check now" for the same verify, when a webhook is slow or lost
   (networks fail, especially here).

Never twice (FR-B4): completing a payment locks its OnlinePayment row; a second webhook,
a retry, or "check now" at the same moment finds it already succeeded and does nothing.
The database backs this up: one Payment per OnlinePayment, one gateway reference per
clinic.

If money arrives after the invoice was settled another way, it is still recorded (the
money is real) and the invoice shows "overpaid", so someone gives the difference back.
"""
import json
import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import SYSTEM_ACTOR_ID, AuditAction, add_audit_event
from app.modules.billing.gateway import GatewayResult, payment_gateway
from app.modules.billing.invoices import locked_invoice, take_number, view_lines
from app.modules.billing.models import (
    InvoiceStatus,
    OnlinePayment,
    OnlinePaymentStatus,
    Payment,
    PaymentMethod,
    ReceiptCounter,
)
from app.modules.billing.money import naira

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL_LENGTH = 200


class InvalidOnlinePaymentError(ValueError):
    """The amount or email is not acceptable, or more than is owed."""


class OnlinePaymentNotAllowedError(Exception):
    """This invoice cannot be paid online now: not issued, or nothing is owed."""


class OnlinePaymentNotFoundError(Exception):
    """No such payment link in this clinic."""


class BadSignatureError(Exception):
    """The webhook was not signed by the gateway: ignore it."""


def _audit(
    session: Session, row: OnlinePayment, *, actor_id: uuid.UUID, action: AuditAction
) -> None:
    add_audit_event(
        session,
        tenant_id=row.tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=row.patient_id,
        entity_id=row.id,
    )


def start_online_payment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    invoice_id: uuid.UUID,
    amount_kobo: int | None = None,
    email: str | None = None,
    online_id: uuid.UUID | None = None,
) -> OnlinePayment:
    """Make a payment link. Asking again for the same amount while one is waiting gives
    the same link, so a patient never gets two links for one bill."""
    if online_id is not None:
        existing = get_in_tenant(session, OnlinePayment, tenant_id=tenant_id, row_id=online_id)
        if isinstance(existing, OnlinePayment):
            return existing
    clean_email = (email or "").strip() or settings.payment_fallback_email
    if len(clean_email) > MAX_EMAIL_LENGTH or not EMAIL.match(clean_email):
        raise InvalidOnlinePaymentError("Give a valid email address, or leave it empty.")

    invoice = locked_invoice(session, tenant_id=tenant_id, invoice_id=invoice_id)
    if invoice.status != InvoiceStatus.ISSUED.value:
        session.rollback()
        raise OnlinePaymentNotAllowedError("Issue the invoice before sending a payment link.")
    owed = view_lines(session, tenant_id=tenant_id, invoice_id=invoice.id).balance_kobo
    if owed <= 0:
        session.rollback()
        raise OnlinePaymentNotAllowedError("This invoice is already paid.")
    amount = owed if amount_kobo is None else amount_kobo
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        session.rollback()
        raise InvalidOnlinePaymentError("The amount must be a whole number of kobo, above zero.")
    if amount > owed:
        session.rollback()
        raise InvalidOnlinePaymentError(f"That is more than the {naira(owed)} still owed.")
    waiting = session.exec(
        tenant_select(OnlinePayment, tenant_id)
        .where(col(OnlinePayment.invoice_id) == invoice.id)
        .where(col(OnlinePayment.status) == OnlinePaymentStatus.PENDING.value)
        .where(col(OnlinePayment.amount_kobo) == amount)
    ).first()
    if waiting is not None:
        session.rollback()
        return waiting
    patient_id, number = invoice.patient_id, invoice.number or ""
    # Let go of the invoice before talking to the gateway: a slow network must not
    # hold up the front desk.
    session.rollback()

    gateway = payment_gateway()
    reference = f"LFY-{secrets.token_hex(12)}"
    link = gateway.initialize(
        reference=reference,
        amount_kobo=amount,
        email=clean_email,
        # The invoice number only: no names or health details go to the gateway.
        metadata={"invoice_number": number},
    )
    row = OnlinePayment(
        id=online_id or uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        patient_id=patient_id,
        gateway=gateway.name,
        reference=reference,
        amount_kobo=amount,
        email=clean_email,
        link=link,
        created_by_id=actor_id,
    )
    session.add(row)
    _audit(session, row, actor_id=actor_id, action=AuditAction.ONLINE_PAYMENT_START)
    session.commit()
    session.refresh(row)
    return row


def _complete(
    session: Session, *, reference: str, result: GatewayResult, actor_id: uuid.UUID
) -> OnlinePayment | None:
    """Act on what the gateway says. Safe to run any number of times for one reference."""
    row = session.exec(
        select(OnlinePayment).where(col(OnlinePayment.reference) == reference).with_for_update()
    ).first()
    if row is None:
        session.rollback()
        return None
    if row.status != OnlinePaymentStatus.PENDING.value:
        session.rollback()  # already settled: the second webhook does nothing
        return row

    now = datetime.now(UTC)
    if result.status == "success":
        if result.currency != "NGN" or result.amount_kobo != row.amount_kobo:
            row.status = OnlinePaymentStatus.FAILED.value
            row.failure_reason = (
                f"The gateway reported {result.amount_kobo} kobo in {result.currency or '?'}, "
                f"not {row.amount_kobo} kobo in NGN. Check it with the gateway."
            )
            row.completed_at = now
            session.add(row)
            _audit(session, row, actor_id=actor_id, action=AuditAction.ONLINE_PAYMENT_FAILED)
            session.commit()
            return row
        locked_invoice(session, tenant_id=row.tenant_id, invoice_id=row.invoice_id)
        payment = Payment(
            tenant_id=row.tenant_id,
            invoice_id=row.invoice_id,
            patient_id=row.patient_id,
            method=PaymentMethod.PAYSTACK.value,
            amount_kobo=row.amount_kobo,
            reference=row.reference,
            receipt_number=take_number(
                session, counter=ReceiptCounter, tenant_id=row.tenant_id, prefix="RCT"
            ),
            received_by_id=row.created_by_id,  # who sent the link
            received_at=now,
        )
        session.add(payment)
        session.flush()
        row.status = OnlinePaymentStatus.SUCCEEDED.value
        row.payment_id = payment.id
        row.gateway_transaction_id = result.transaction_id
        row.completed_at = now
        session.add(row)
        _audit(session, row, actor_id=actor_id, action=AuditAction.ONLINE_PAYMENT_PAID)
        session.commit()
        session.refresh(row)
        return row
    if result.status in ("failed", "abandoned", "reversed"):
        row.status = OnlinePaymentStatus.FAILED.value
        row.failure_reason = f"The gateway says the payment {result.status}."
        row.completed_at = now
        session.add(row)
        _audit(session, row, actor_id=actor_id, action=AuditAction.ONLINE_PAYMENT_FAILED)
        session.commit()
        return row
    session.rollback()  # still pending: nothing to do yet
    return row


def handle_webhook(session: Session, *, body: bytes, signature: str | None) -> str:
    """A gateway webhook. Answers what was done, for the server log; the gateway only
    needs a 200. Raises BadSignatureError for a fake, GatewayUnavailableError when the
    gateway cannot be asked (the gateway will then send it again later)."""
    gateway = payment_gateway()
    if not gateway.signature_ok(body, signature):
        raise BadSignatureError("The webhook signature is wrong.")
    try:
        event = json.loads(body)
    except ValueError:
        return "ignored: not JSON"
    if not isinstance(event, dict) or event.get("event") != "charge.success":
        return "ignored: not a charge.success"
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    reference = str(data.get("reference", ""))
    known = session.exec(
        select(OnlinePayment).where(col(OnlinePayment.reference) == reference)
    ).first()
    if known is None:
        return "ignored: unknown reference"
    # The webhook is a hint; the gateway's own answer is the truth.
    result = gateway.verify(reference=reference)
    row = _complete(session, reference=reference, result=result, actor_id=SYSTEM_ACTOR_ID)
    return f"{row.status if row else 'unknown'}: {reference}"


def check_online_payment(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, online_id: uuid.UUID
) -> OnlinePayment:
    """Staff press "check now": ask the gateway, and record the payment if it went through."""
    row = get_in_tenant(session, OnlinePayment, tenant_id=tenant_id, row_id=online_id)
    if not isinstance(row, OnlinePayment):
        raise OnlinePaymentNotFoundError("Payment link not found.")
    if row.status != OnlinePaymentStatus.PENDING.value:
        return row
    result = payment_gateway().verify(reference=row.reference)
    done = _complete(session, reference=row.reference, result=result, actor_id=actor_id)
    if done is not None and done.status == OnlinePaymentStatus.PENDING.value:
        _audit(session, done, actor_id=actor_id, action=AuditAction.ONLINE_PAYMENT_CHECK)
        session.commit()
    return done or row
