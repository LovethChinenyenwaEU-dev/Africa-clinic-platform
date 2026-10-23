"""Refunds with two people (Week 10 Step 4, FR-B3).

Front desk or billing asks for a refund from one payment: how much, how the money goes
back (cash or transfer) and why. An admin approves or rejects it, and never a request
they made themselves (checked here and by the database). Only an approved refund gives
money back; an approval gets the clinic's next refund number.

One payment can never be refunded beyond what it brought in: requests still waiting
count too, so two requests cannot together give back more than was paid. The invoice
is locked while this is worked out.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.billing.invoices import locked_invoice, take_number
from app.modules.billing.models import (
    MANUAL_METHODS,
    Payment,
    PaymentMethod,
    Refund,
    RefundCounter,
    RefundStatus,
)
from app.modules.billing.money import naira

MIN_TEXT_LENGTH = 3
MAX_TEXT_LENGTH = 300
STILL_COUNTING = (RefundStatus.REQUESTED.value, RefundStatus.APPROVED.value)


class InvalidRefundError(ValueError):
    """The amount, method or reason is not acceptable, or more than can be given back."""


class RefundNotFoundError(Exception):
    """No such refund or payment in this clinic."""


class RefundAlreadyDecidedError(Exception):
    """This refund was already approved or rejected."""


class OwnRefundError(Exception):
    """Whoever asked for a refund cannot decide it."""


def _text(value: str, what: str) -> str:
    clean = " ".join(value.split())
    if not MIN_TEXT_LENGTH <= len(clean) <= MAX_TEXT_LENGTH:
        raise InvalidRefundError(
            f"The {what} must be {MIN_TEXT_LENGTH} to {MAX_TEXT_LENGTH} characters."
        )
    return clean


def _refundable(session: Session, *, tenant_id: uuid.UUID, payment: Payment) -> int:
    """What can still be asked back from this payment."""
    statement = (
        tenant_select(Refund, tenant_id)
        .where(col(Refund.payment_id) == payment.id)
        .where(col(Refund.status).in_(STILL_COUNTING))
    )
    taken = sum(refund.amount_kobo for refund in session.exec(statement).all())
    return payment.amount_kobo - taken


def _audit(session: Session, refund: Refund, *, actor_id: uuid.UUID, action: AuditAction) -> None:
    add_audit_event(
        session,
        tenant_id=refund.tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=refund.patient_id,
        entity_id=refund.id,
    )


def request_refund(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount_kobo: int,
    method: str,
    reason: str,
    refund_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Refund:
    """Ask for money back from one payment. Sending the same ID twice asks once."""
    if refund_id is not None:
        existing = get_in_tenant(session, Refund, tenant_id=tenant_id, row_id=refund_id)
        if isinstance(existing, Refund):
            return existing
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, int) or amount_kobo <= 0:
        raise InvalidRefundError("The amount must be a whole number of kobo, above zero.")
    if method not in MANUAL_METHODS:
        raise InvalidRefundError("The money goes back as cash or transfer.")
    kind = PaymentMethod(method).value
    clean_reason = _text(reason, "reason")
    payment = get_in_tenant(session, Payment, tenant_id=tenant_id, row_id=payment_id)
    if not isinstance(payment, Payment):
        raise RefundNotFoundError("Payment not found.")

    # Lock the invoice: two requests at once wait for each other.
    locked_invoice(session, tenant_id=tenant_id, invoice_id=payment.invoice_id)
    left = _refundable(session, tenant_id=tenant_id, payment=payment)
    if amount_kobo > left:
        session.rollback()
        raise InvalidRefundError(
            f"At most {naira(max(left, 0))} of this payment can still be given back."
        )

    refund = Refund(
        id=refund_id or uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=payment.invoice_id,
        payment_id=payment.id,
        patient_id=payment.patient_id,
        amount_kobo=amount_kobo,
        method=kind,
        reason=clean_reason,
        requested_by_id=actor_id,
        requested_at=now or datetime.now(UTC),
    )
    session.add(refund)
    _audit(session, refund, actor_id=actor_id, action=AuditAction.REFUND_REQUEST)
    session.commit()
    session.refresh(refund)
    return refund


def _waiting(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, refund_id: uuid.UUID
) -> Refund:
    statement = (
        tenant_select(Refund, tenant_id).where(col(Refund.id) == refund_id).with_for_update()
    )
    refund = session.exec(statement).first()
    if refund is None:
        raise RefundNotFoundError("Refund not found.")
    if refund.status != RefundStatus.REQUESTED.value:
        session.rollback()
        raise RefundAlreadyDecidedError(f"This refund is already {refund.status}.")
    if refund.requested_by_id == actor_id:
        session.rollback()
        raise OwnRefundError("Someone else must decide a refund you asked for.")
    return refund


def approve_refund(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    refund_id: uuid.UUID,
    note: str | None = None,
    now: datetime | None = None,
) -> Refund:
    """Approve: the money goes back, and the refund gets its number."""
    clean_note = _text(note, "note") if note and note.strip() else None
    refund = _waiting(session, tenant_id=tenant_id, actor_id=actor_id, refund_id=refund_id)
    # Take the number BEFORE changing the status: taking it queries the database, which
    # first saves pending changes, and "approved without a number" breaks a check.
    number = take_number(session, counter=RefundCounter, tenant_id=tenant_id, prefix="RFD")
    refund.status = RefundStatus.APPROVED.value
    refund.refund_number = number
    refund.decided_by_id = actor_id
    refund.decided_at = now or datetime.now(UTC)
    refund.decision_note = clean_note
    session.add(refund)
    _audit(session, refund, actor_id=actor_id, action=AuditAction.REFUND_APPROVE)
    session.commit()
    session.refresh(refund)
    return refund


def reject_refund(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    refund_id: uuid.UUID,
    note: str,
    now: datetime | None = None,
) -> Refund:
    """Reject, saying why. The amount can then be asked for again if needed."""
    clean_note = _text(note, "note")
    refund = _waiting(session, tenant_id=tenant_id, actor_id=actor_id, refund_id=refund_id)
    refund.status = RefundStatus.REJECTED.value
    refund.decided_by_id = actor_id
    refund.decided_at = now or datetime.now(UTC)
    refund.decision_note = clean_note
    session.add(refund)
    _audit(session, refund, actor_id=actor_id, action=AuditAction.REFUND_REJECT)
    session.commit()
    session.refresh(refund)
    return refund


def list_refunds(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    status: str | None = RefundStatus.REQUESTED.value,
) -> list[Refund]:
    """Refunds of the clinic, oldest first: by default those waiting for a decision.
    Written in the diary: it shows which patients were refunded."""
    statement = tenant_select(Refund, tenant_id).order_by(
        col(Refund.requested_at), col(Refund.id)
    )
    if status is not None:
        try:
            wanted = RefundStatus(status).value
        except ValueError:
            raise InvalidRefundError(
                "Status must be requested, approved or rejected."
            ) from None
        statement = statement.where(col(Refund.status) == wanted)
    rows = list(session.exec(statement).all())
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.REFUND_LIST
    )
    session.commit()
    return rows
