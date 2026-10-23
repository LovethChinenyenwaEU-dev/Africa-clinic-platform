"""Doors for billing. Step 1: the price list.

Everyone who books or takes payments reads the price list; only an admin
changes it. Changes are POSTs, because the staff pass-through only sends GET and POST.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.billing.prices import (
    InvalidPriceError,
    PriceNameTakenError,
    PriceNotFoundError,
    add_price,
    change_price,
    list_prices,
)
from app.modules.billing.schemas import AddPrice, ChangePrice, PriceResponse
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
