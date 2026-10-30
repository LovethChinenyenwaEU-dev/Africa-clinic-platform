import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.mfa import OwnResetError, reset_mfa
from app.modules.identity.models import Staff
from app.modules.identity.passwords import WeakPasswordError
from app.modules.identity.permissions import Capability
from app.modules.identity.schemas import (
    ClinicianResponse,
    DeviceResponse,
    StaffCreate,
    StaffResponse,
)
from app.modules.identity.service import (
    EmailAlreadyUsedError,
    InvalidRoleError,
    LastAdminError,
    StaffNotFoundError,
    create_staff,
    list_active_clinicians,
    list_staff,
    set_staff_active,
)
from app.modules.identity.sessions import (
    SessionNotFoundError,
    current_session_id,
    end_session,
    list_devices,
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


@router.get(
    "/clinicians",
    response_model=list[ClinicianResponse],
    dependencies=[Depends(require(Capability.APPOINTMENT_READ))],
)
def list_my_clinicians(
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Active doctors and nurses, for anyone who books visits. Names and roles only."""
    return list_active_clinicians(session, tenant_id=current_staff.tenant_id)


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
            status_code=422,
            detail=str(error),
        ) from None
    except EmailAlreadyUsedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A staff member with this email already exists.",
        ) from None


# Signed-in devices (Week 11). The /me routes are declared before /{staff_id}, so "me" is
# never read as a staff id.


def _devices(session: Session, current_staff: CurrentStaff, staff_id: uuid.UUID):
    if not _same_clinic(session, current_staff, staff_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    views = list_devices(
        session,
        tenant_id=current_staff.tenant_id,
        staff_id=staff_id,
        current_session_id=current_session_id(session),
    )
    return [
        DeviceResponse(
            id=view.session.id,
            label=view.session.label,
            created_at=view.session.created_at,
            last_seen_at=view.session.last_seen_at,
            current=view.current,
        )
        for view in views
    ]


def _end(session: Session, current_staff: CurrentStaff, staff_id: uuid.UUID, sid: uuid.UUID):
    try:
        end_session(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            staff_id=staff_id,
            session_id=sid,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from None
    return {"signed_out": True}  # 200 with a body: the staff pass-through cannot carry a 204


def _same_clinic(session: Session, current_staff: CurrentStaff, staff_id: uuid.UUID) -> bool:
    staff = session.get(Staff, staff_id)
    return staff is not None and staff.tenant_id == current_staff.tenant_id


@router.get("/me/sessions", response_model=list[DeviceResponse])
def list_my_devices(current_staff: CurrentStaff, session: Session = Depends(get_session)):
    """Where am I signed in? Any staff member, for their own devices."""
    return _devices(session, current_staff, current_staff.id)


@router.post("/me/sessions/{sid}/end")
def end_my_device(
    sid: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Sign one of my devices out (a phone left at the clinic, a shared computer)."""
    return _end(session, current_staff, current_staff.id, sid)


@router.get(
    "/{staff_id}/sessions",
    response_model=list[DeviceResponse],
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def list_staff_devices(
    staff_id: uuid.UUID, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """An admin sees where a staff member of the clinic is signed in."""
    return _devices(session, current_staff, staff_id)


@router.post(
    "/{staff_id}/sessions/{sid}/end",
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def end_staff_device(
    staff_id: uuid.UUID,
    sid: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """An admin signs one of a staff member's devices out (a lost or stolen phone)."""
    return _end(session, current_staff, staff_id, sid)


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


@router.post(
    "/{staff_id}/mfa/reset",
    dependencies=[Depends(require(Capability.STAFF_MANAGE))],
)
def reset_staff_mfa(
    staff_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """A lost phone: clear this person's authenticator app. They set it up again at their
    next sign-in. Another admin must do it; nobody resets their own."""
    try:
        reset_mfa(
            session, tenant_id=current_staff.tenant_id, actor_id=current_staff.id, staff_id=staff_id
        )
    except OwnResetError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from None
    except StaffNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from None
    return {"reset": True}  # 200 with a body: the staff pass-through cannot carry a 204
