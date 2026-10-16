"""Doors for clinicians' weekly hours and free slots (FR-C1).

A clinician publishes and removes their own hours. Anyone who books visits (front
desk, nurses, doctors) can read any clinician's hours and free slots: they hold
no patient data.
"""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.scheduling.availability import (
    AvailabilityNotFoundError,
    AvailabilityOverlapError,
    InvalidAvailabilityError,
    NotAClinicianForHoursError,
    add_availability,
    free_slots,
    list_availability,
    remove_availability,
)
from app.modules.scheduling.schemas import HoursResponse, PublishHours, SlotResponse
from app.modules.scheduling.service import BranchNotFoundError

router = APIRouter(prefix="/availability", tags=["availability"])

READ = [Depends(require(Capability.APPOINTMENT_READ))]
PUBLISH = [Depends(require(Capability.APPOINTMENT_CONSULT))]  # doctors and nurses
KNOWN_ERRORS = (
    InvalidAvailabilityError,
    AvailabilityOverlapError,
    AvailabilityNotFoundError,
    NotAClinicianForHoursError,
    BranchNotFoundError,
)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidAvailabilityError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, AvailabilityOverlapError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, AvailabilityNotFoundError | BranchNotFoundError):
        return HTTPException(status_code=404, detail="Not found.")
    if isinstance(error, NotAClinicianForHoursError):
        return HTTPException(status_code=403, detail=str(error))
    raise error


@router.get("", response_model=list[HoursResponse], dependencies=READ)
def read_hours(
    current_staff: CurrentStaff,
    clinician_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """One clinician's weekly hours, Monday first."""
    return list_availability(session, tenant_id=current_staff.tenant_id, clinician_id=clinician_id)


@router.post(
    "", response_model=HoursResponse, status_code=status.HTTP_201_CREATED, dependencies=PUBLISH
)
def publish_hours(
    body: PublishHours, current_staff: CurrentStaff, session: Session = Depends(get_session)
):
    """Publish weekly hours for yourself."""
    try:
        return add_availability(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            branch_id=body.branch_id,
            weekday=body.weekday,
            starts=body.starts,
            ends=body.ends,
            visit_type=body.visit_type,
            slot_minutes=body.slot_minutes,
            availability_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/{availability_id}/remove", response_model=HoursResponse, dependencies=PUBLISH
)
def remove_hours(
    availability_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Stop offering these hours (your own only). Answers with the hours removed.
    Visits already booked in them are not touched."""
    try:
        return remove_availability(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            availability_id=availability_id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get("/slots", response_model=list[SlotResponse], dependencies=READ)
def read_free_slots(
    current_staff: CurrentStaff,
    clinician_id: uuid.UUID,
    visit_type: str,
    from_day: date,
    days: Annotated[int, Query(ge=1, le=14)] = 7,
    session: Session = Depends(get_session),
):
    """Free slots of one clinician, from a Lagos day, earliest first."""
    try:
        return free_slots(
            session,
            tenant_id=current_staff.tenant_id,
            clinician_id=clinician_id,
            visit_type=visit_type,
            from_day=from_day,
            days=days,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
