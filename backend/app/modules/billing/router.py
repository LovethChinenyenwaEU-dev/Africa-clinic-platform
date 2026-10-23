"""Doors for billing. Step 1: the price list. Step 2: invoices.

Everyone who books or takes payments reads the price list; only an admin
changes it. Front desk and billing build and issue invoices; admins read them.
Changes are POSTs, because the staff pass-through only sends GET and POST.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.billing.invoices import (
    InvalidInvoiceError,
    InvoiceLockedError,
    InvoiceNotFoundError,
    InvoiceView,
    add_line,
    issue_invoice,
    list_patient_invoices,
    remove_line,
    start_invoice,
    view_invoice,
    view_lines,
    view_visit_invoice,
    void_invoice,
)
from app.modules.billing.prices import (
    InvalidPriceError,
    PriceNameTakenError,
    PriceNotFoundError,
    add_price,
    change_price,
    list_prices,
)
from app.modules.billing.schemas import (
    AddInvoiceLine,
    AddPrice,
    ChangePrice,
    InvoiceLineResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    PriceResponse,
    StartInvoice,
    VoidInvoice,
)
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability

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


def _answer(result: InvoiceView) -> InvoiceResponse:
    summary = InvoiceSummaryResponse.model_validate(result.invoice)
    lines = [InvoiceLineResponse.model_validate(line) for line in result.lines]
    return InvoiceResponse(**summary.model_dump(), lines=lines)


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
    """A patient's invoices, newest first."""
    try:
        return list_patient_invoices(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
        )
    except INVOICE_ERRORS as error:
        raise _invoice_error(error) from None


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
