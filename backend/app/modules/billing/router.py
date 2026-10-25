"""Doors for billing (Week 10): prices, invoices, payments and receipts, refunds,
Paystack, and the daily takings.

Everyone who books or takes payments reads the price list; only an admin
changes it. Front desk and billing build invoices, take money and ask for refunds;
admins read invoices, decide refunds and, with billing, read the takings.
Changes are POSTs, because the staff pass-through only sends GET and POST.
"""
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session

from app.core.db import get_session
from app.modules.billing.gateway import GatewayUnavailableError
from app.modules.billing.invoices import (
    InvalidInvoiceError,
    InvoiceLockedError,
    InvoiceNotFoundError,
    InvoiceView,
    add_line,
    billable_visits,
    issue_invoice,
    list_patient_invoices,
    remove_line,
    start_invoice,
    view_invoice,
    view_lines,
    view_visit_invoice,
    void_invoice,
)
from app.modules.billing.online import (
    BadSignatureError,
    InvalidOnlinePaymentError,
    OnlinePaymentNotAllowedError,
    OnlinePaymentNotFoundError,
    check_online_payment,
    handle_webhook,
    start_online_payment,
)
from app.modules.billing.payments import (
    DuplicateTransferError,
    InvalidPaymentError,
    PaymentNotAllowedError,
    PaymentNotFoundError,
    record_payment,
    view_receipt,
)
from app.modules.billing.prices import (
    InvalidPriceError,
    PriceNameTakenError,
    PriceNotFoundError,
    add_price,
    change_price,
    list_prices,
)
from app.modules.billing.refunds import (
    InvalidRefundError,
    OwnRefundError,
    RefundAlreadyDecidedError,
    RefundNotFoundError,
    approve_refund,
    list_refunds,
    reject_refund,
    request_refund,
)
from app.modules.billing.schemas import (
    AddInvoiceLine,
    AddPrice,
    ChangePrice,
    DecideRefund,
    InvoiceLineResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    OnlinePaymentResponse,
    PaymentResponse,
    PriceResponse,
    ReceiptResponse,
    RecordPayment,
    RefundResponse,
    RequestRefund,
    StartInvoice,
    StartOnlinePayment,
    TakingsExportResponse,
    TakingsResponse,
    VisitToBillResponse,
    VoidInvoice,
)
from app.modules.billing.takings import daily_takings, takings_csv
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.scheduling.board import lagos_day

router = APIRouter(prefix="/billing", tags=["billing"])

READ_PRICES = [Depends(require(Capability.PRICE_READ))]
WRITE_PRICES = [Depends(require(Capability.PRICE_WRITE))]  # admins only


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidPriceError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, PriceNameTakenError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, PriceNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    raise error


@router.get("/prices", response_model=list[PriceResponse], dependencies=READ_PRICES)
def read_prices(
    current_staff: CurrentStaff,
    include_retired: bool = False,
    session: Session = Depends(get_session),
):
    """The clinic's services, A to Z. Retired ones too with include_retired=true."""
    return list_prices(
        session, tenant_id=current_staff.tenant_id, include_retired=include_retired
    )


@router.post(
    "/prices",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE_PRICES,
)
def add_service(
    body: AddPrice, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Add a service to the price list."""
    try:
        return add_price(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            name=body.name,
            code=body.code,
            price_kobo=body.price_kobo,
            price_id=body.id,
        )
    except (InvalidPriceError, PriceNameTakenError) as error:
        raise _http_error(error) from None


@router.post("/prices/{price_id}", response_model=PriceResponse, dependencies=WRITE_PRICES)
def change_service(
    price_id: uuid.UUID,
    body: ChangePrice,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Change a service, or retire it (active false) or bring it back."""
    try:
        return change_price(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            price_id=price_id,
            name=body.name,
            code=body.code,
            price_kobo=body.price_kobo,
            active=body.active,
        )
    except (InvalidPriceError, PriceNameTakenError, PriceNotFoundError) as error:
        raise _http_error(error) from None


# --- invoices (Step 2) -------------------------------------------------------------

READ_INVOICES = [Depends(require(Capability.INVOICE_READ))]
WRITE_INVOICES = [Depends(require(Capability.INVOICE_WRITE))]  # front desk and billing
INVOICE_ERRORS = (InvalidInvoiceError, InvoiceNotFoundError, InvoiceLockedError)


def _invoice_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidInvoiceError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, InvoiceLockedError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, InvoiceNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    raise error


def _summary(result: InvoiceView) -> InvoiceSummaryResponse:
    summary = InvoiceSummaryResponse.model_validate(result.invoice)
    return summary.model_copy(
        update={
            "paid_kobo": result.paid_kobo,
            "refunded_kobo": result.refunded_kobo,
            "balance_kobo": result.balance_kobo,
            "credit_kobo": result.credit_kobo,
            "payment_status": result.payment_status.value,
        }
    )


def _answer(result: InvoiceView) -> InvoiceResponse:
    return InvoiceResponse(
        **_summary(result).model_dump(),
        lines=[InvoiceLineResponse.model_validate(line) for line in result.lines],
        payments=[PaymentResponse.model_validate(payment) for payment in result.payments],
        refunds=[RefundResponse.model_validate(refund) for refund in result.refunds],
        online_payments=[
            OnlinePaymentResponse.model_validate(row) for row in result.online_payments
        ],
    )


@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE_INVOICES,
)
def start_visit_invoice(
    body: StartInvoice, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Start the invoice for a visit, or get the one it already has."""
    try:
        invoice = start_invoice(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=body.appointment_id,
            invoice_id=body.id,
        )
        result = view_lines(session, tenant_id=current_staff.tenant_id, invoice_id=invoice.id)
        return _answer(result)
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse, dependencies=READ_INVOICES)
def read_invoice(
    invoice_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """One invoice with its lines."""
    try:
        return _answer(
            view_invoice(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                invoice_id=invoice_id,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.get(
    "/visits/{appointment_id}/invoice",
    response_model=InvoiceResponse,
    dependencies=READ_INVOICES,
)
def read_visit_invoice(
    appointment_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """The visit's invoice (not a voided one), or 404 if it has none yet."""
    try:
        return _answer(
            view_visit_invoice(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                appointment_id=appointment_id,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.get(
    "/patients/{patient_id}/invoices",
    response_model=list[InvoiceSummaryResponse],
    dependencies=READ_INVOICES,
)
def read_patient_invoices(
    patient_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """A patient's invoices, newest first, with what is paid and still owed."""
    try:
        views = list_patient_invoices(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
        )
        return [_summary(view) for view in views]
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.get(
    "/patients/{patient_id}/visits",
    response_model=list[VisitToBillResponse],
    dependencies=READ_INVOICES,
)
def read_visits_to_bill(
    patient_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """A patient's recent visits, newest first, each with its invoice (or none yet)."""
    try:
        rows = billable_visits(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None
    return [
        VisitToBillResponse(
            appointment_id=row.appointment_id,
            starts_at=row.starts_at,
            status=row.status,
            visit_type=row.visit_type,
            invoice=_summary(row.invoice) if row.invoice else None,
        )
        for row in rows
    ]


@router.post(
    "/invoices/{invoice_id}/lines",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=WRITE_INVOICES,
)
def add_invoice_line(
    invoice_id: uuid.UUID,
    body: AddInvoiceLine,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Add a service from the price list to a draft."""
    try:
        return _answer(
            add_line(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                invoice_id=invoice_id,
                price_item_id=body.price_item_id,
                quantity=body.quantity,
                line_id=body.id,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.post(
    "/invoices/{invoice_id}/lines/{line_id}/remove",
    response_model=InvoiceResponse,
    dependencies=WRITE_INVOICES,
)
def remove_invoice_line(
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Take a line off a draft."""
    try:
        return _answer(
            remove_line(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                invoice_id=invoice_id,
                line_id=line_id,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.post(
    "/invoices/{invoice_id}/issue", response_model=InvoiceResponse, dependencies=WRITE_INVOICES
)
def issue_visit_invoice(
    invoice_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Number and freeze the invoice."""
    try:
        return _answer(
            issue_invoice(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                invoice_id=invoice_id,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


@router.post(
    "/invoices/{invoice_id}/void", response_model=InvoiceResponse, dependencies=WRITE_INVOICES
)
def void_visit_invoice(
    invoice_id: uuid.UUID,
    body: VoidInvoice,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Cancel a draft made by mistake, with the reason."""
    try:
        return _answer(
            void_invoice(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                invoice_id=invoice_id,
                reason=body.reason,
            )
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


# --- payments and receipts (Step 3) -----------------------------------------------

TAKE_PAYMENTS = [Depends(require(Capability.PAYMENT_RECORD))]  # front desk and billing


def _payment_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidPaymentError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, PaymentNotAllowedError | DuplicateTransferError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, PaymentNotFoundError | InvoiceNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    raise error


PAYMENT_ERRORS = (
    InvalidPaymentError,
    PaymentNotAllowedError,
    DuplicateTransferError,
    PaymentNotFoundError,
    InvoiceNotFoundError,
)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=TAKE_PAYMENTS,
)
def take_payment(
    invoice_id: uuid.UUID,
    body: RecordPayment,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Record cash or a bank transfer against an issued invoice. Never more than is owed."""
    try:
        return record_payment(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            invoice_id=invoice_id,
            method=body.method,
            amount_kobo=body.amount_kobo,
            reference=body.reference,
            payment_id=body.id,
        )
    except PAYMENT_ERRORS as error:
        raise _payment_error(error) from None


@router.get(
    "/payments/{payment_id}/receipt", response_model=ReceiptResponse, dependencies=READ_INVOICES
)
def read_receipt(
    payment_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Everything the printed receipt shows, with its check code."""
    try:
        receipt = view_receipt(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            payment_id=payment_id,
        )
    except PAYMENT_ERRORS as error:
        raise _payment_error(error) from None
    return ReceiptResponse(
        payment=PaymentResponse.model_validate(receipt.payment),
        clinic_name=receipt.clinic_name,
        patient_name=receipt.patient_name,
        invoice_number=receipt.invoice_number,
        invoice_total_kobo=receipt.invoice_total_kobo,
        paid_to_date_kobo=receipt.paid_to_date_kobo,
        balance_after_kobo=receipt.balance_after_kobo,
        received_by_name=receipt.received_by_name,
        check_code=receipt.check_code,
    )


# --- refunds (Step 4) ---------------------------------------------------------------

ASK_REFUNDS = [Depends(require(Capability.REFUND_REQUEST))]  # front desk and billing
DECIDE_REFUNDS = [Depends(require(Capability.REFUND_APPROVE))]  # admins
REFUND_ERRORS = (
    InvalidRefundError,
    RefundNotFoundError,
    RefundAlreadyDecidedError,
    OwnRefundError,
    InvoiceNotFoundError,
)


def _refund_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidRefundError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, RefundAlreadyDecidedError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, OwnRefundError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, RefundNotFoundError | InvoiceNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    raise error


@router.post(
    "/payments/{payment_id}/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=ASK_REFUNDS,
)
def ask_for_refund(
    payment_id: uuid.UUID,
    body: RequestRefund,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Ask for money back from one payment. An admin decides."""
    try:
        return request_refund(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            payment_id=payment_id,
            amount_kobo=body.amount_kobo,
            method=body.method,
            reason=body.reason,
            refund_id=body.id,
        )
    except REFUND_ERRORS as error:
        raise _refund_error(error) from None


@router.get("/refunds", response_model=list[RefundResponse], dependencies=DECIDE_REFUNDS)
def read_refunds(
    current_staff: CurrentStaff,
    status: str | None = "requested",
    session: Session = Depends(get_session),
):
    """Refunds of the clinic, oldest first. Waiting ones by default; status=approved or
    rejected for the others."""
    try:
        return list_refunds(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            status=status,
        )
    except REFUND_ERRORS as error:
        raise _refund_error(error) from None


@router.post(
    "/refunds/{refund_id}/approve", response_model=RefundResponse, dependencies=DECIDE_REFUNDS
)
def approve(
    refund_id: uuid.UUID,
    body: DecideRefund,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Approve a refund someone else asked for."""
    try:
        return approve_refund(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            refund_id=refund_id,
            note=body.note,
        )
    except REFUND_ERRORS as error:
        raise _refund_error(error) from None


@router.post(
    "/refunds/{refund_id}/reject", response_model=RefundResponse, dependencies=DECIDE_REFUNDS
)
def reject(
    refund_id: uuid.UUID,
    body: DecideRefund,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Reject a refund someone else asked for, saying why."""
    try:
        return reject_refund(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            refund_id=refund_id,
            note=body.note or "",
        )
    except REFUND_ERRORS as error:
        raise _refund_error(error) from None


# --- online payment through the gateway (Step 5) -----------------------------------

ONLINE_ERRORS = (
    InvalidOnlinePaymentError,
    OnlinePaymentNotAllowedError,
    OnlinePaymentNotFoundError,
    GatewayUnavailableError,
    InvoiceNotFoundError,
)


def _online_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidOnlinePaymentError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, OnlinePaymentNotAllowedError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, OnlinePaymentNotFoundError | InvoiceNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    if isinstance(error, GatewayUnavailableError):
        return HTTPException(status_code=503, detail=str(error))
    raise error


@router.post(
    "/invoices/{invoice_id}/online-payments",
    response_model=OnlinePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=TAKE_PAYMENTS,
)
def send_payment_link(
    invoice_id: uuid.UUID,
    body: StartOnlinePayment,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Make a payment link for an issued invoice (by default for everything owed)."""
    try:
        return start_online_payment(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            invoice_id=invoice_id,
            amount_kobo=body.amount_kobo,
            email=body.email,
            online_id=body.id,
        )
    except ONLINE_ERRORS as error:
        raise _online_error(error) from None


@router.post(
    "/online-payments/{online_id}/check",
    response_model=OnlinePaymentResponse,
    dependencies=TAKE_PAYMENTS,
)
def check_payment_link(
    online_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Ask the gateway now, instead of waiting for its webhook."""
    try:
        return check_online_payment(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            online_id=online_id,
        )
    except ONLINE_ERRORS as error:
        raise _online_error(error) from None


@router.post("/paystack/webhook")
async def paystack_webhook(request: Request, session: Session = Depends(get_session)):
    """Paystack's call when a payment changes. Public, but only a correctly signed call
    is read, and no money is counted until Paystack's own verify agrees."""
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    try:
        outcome = await run_in_threadpool(
            handle_webhook, session, body=body, signature=signature
        )
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Bad signature.") from None
    except GatewayUnavailableError:
        # Paystack sends the webhook again later; by then it may answer verify.
        raise HTTPException(status_code=503, detail="Try again later.") from None
    return {"received": True, "outcome": outcome}


# --- the daily takings (Step 6) ---------------------------------------------------------

READ_TAKINGS = [Depends(require(Capability.TAKINGS_READ))]  # admins and billing


def _day(day: date | None) -> date:
    return day or lagos_day(datetime.now(UTC))


@router.get("/takings", response_model=TakingsResponse, dependencies=READ_TAKINGS)
def read_takings(
    current_staff: CurrentStaff,
    day: date | None = None,
    session: Session = Depends(get_session),
):
    """One Lagos day's money in and out, by method and person, and what to look at.
    Today when no day is given."""
    result = daily_takings(
        session, tenant_id=current_staff.tenant_id, actor_id=current_staff.id, day=_day(day)
    )
    return TakingsResponse.model_validate(result)


@router.get("/takings/export", response_model=TakingsExportResponse, dependencies=READ_TAKINGS)
def export_takings(
    current_staff: CurrentStaff,
    day: date | None = None,
    session: Session = Depends(get_session),
):
    """The day's payments and refunds as CSV (no patient names)."""
    filename, text = takings_csv(
        session, tenant_id=current_staff.tenant_id, actor_id=current_staff.id, day=_day(day)
    )
    return TakingsExportResponse(filename=filename, csv=text)
