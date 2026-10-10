import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.passwords import WeakPasswordError
from app.modules.identity.permissions import Capability
from app.modules.identity.schemas import StaffCreate, StaffResponse
from app.modules.identity.service import (
    EmailAlreadyUsedError,
    InvalidRoleError,
    LastAdminError,
    StaffNotFoundError,
    create_staff,
    list_staff,
    set_staff_active,
)

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get(
    "",
    response_model=list[StaffResponse],
    dependencies=[Depends(require(Capability.STAFF_READ))],
)
def list_my_staff(
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The staff of the logged-in admin's own clinic."""
    return list_staff(session, tenant_id=current_staff.tenant_id)


@router.post(
    "",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def add_staff(
    body: StaffCreate,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Add a staff member to the logged-in admin's own clinic."""
    try:
        return create_staff(
            session,
            tenant_id=current_staff.tenant_id,
            email=body.email,
            full_name=body.full_name,
            role=body.role,
            password=body.password,
        )
    except (WeakPasswordError, InvalidRoleError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None
    except EmailAlreadyUsedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A staff member with this email already exists.",
        ) from None


def _switch(session: Session, current_staff: CurrentStaff, staff_id: uuid.UUID, active: bool):
    try:
        return set_staff_active(
            session,
            tenant_id=current_staff.tenant_id,
            staff_id=staff_id,
            active=active,
        )
    except StaffNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        ) from None
    except LastAdminError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None


@router.post(
    "/{staff_id}/deactivate",
    response_model=StaffResponse,
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def deactivate_staff(
    staff_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Switch a staff member off. They lose access immediately."""
    return _switch(session, current_staff, staff_id, active=False)


@router.post(
    "/{staff_id}/activate",
    response_model=StaffResponse,
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def activate_staff(
    staff_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Switch a staff member back on."""
    return _switch(session, current_staff, staff_id, active=True)