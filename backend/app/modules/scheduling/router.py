import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.patients.service import PatientNotFoundError
from app.modules.scheduling.board import get_queue
from app.modules.scheduling.lifecycle import (
    AppointmentNotFoundError,
    ClinicianMismatchError,
    cancel_appointment,
    check_in,
    complete_consultation,
    mark_no_show,
    reschedule_appointment,
    start_consultation,
)
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.schemas import (
    AppointmentResponse,
    BookAppointment,
    QueueEntryResponse,
    RescheduleAppointment,
    WalkInRegistration,
)
from app.modules.scheduling.service import (
    BranchNotFoundError,
    ClinicianNotFoundError,
    InvalidAppointmentError,
    SlotTakenError,
    book_appointment,
    register_walk_in,
)
from app.modules.scheduling.transitions import InvalidMoveError

router = APIRouter(prefix="/appointments", tags=["appointments"])

# One shared message for all three, so a snoop cannot tell which of them exists elsewhere.
REFERENCE_NOT_FOUND = "Patient, branch or clinician not found."
APPOINTMENT_NOT_FOUND = "Appointment not found."

KNOWN_ERRORS = (
    InvalidAppointmentError,
    PatientNotFoundError,
    BranchNotFoundError,
    ClinicianNotFoundError,
    AppointmentNotFoundError,
    SlotTakenError,
    InvalidMoveError,
    ClinicianMismatchError,
)


def _http_error(error: Exception) -> HTTPException:
    """Turn our own named errors into answers. Nothing unexpected is ever caught."""
    if isinstance(error, InvalidAppointmentError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, PatientNotFoundError | BranchNotFoundError | ClinicianNotFoundError):
        return HTTPException(status_code=404, detail=REFERENCE_NOT_FOUND)
    if isinstance(error, AppointmentNotFoundError):
        return HTTPException(status_code=404, detail=APPOINTMENT_NOT_FOUND)
    if isinstance(error, SlotTakenError | InvalidMoveError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ClinicianMismatchError):
        return HTTPException(status_code=403, detail=str(error))
    raise error


def _change(
    action: Callable[..., Appointment],
    session: Session,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
) -> Appointment:
    try:
        return action(
            session, tenant_id=tenant_id, actor_id=actor_id, appointment_id=appointment_id
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def book_visit(
    body: BookAppointment,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Book a visit ahead of time at the logged-in person's own clinic."""
    try:
        return book_appointment(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=body.patient_id,
            branch_id=body.branch_id,
            clinician_id=body.clinician_id,
            starts_at=body.starts_at,
            duration_minutes=body.duration_minutes,
            visit_type=body.visit_type,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/walk-ins",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def register_arrival(
    body: WalkInRegistration,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """A patient arrived without a booking and joins the queue."""
    try:
        return register_walk_in(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=body.patient_id,
            branch_id=body.branch_id,
            clinician_id=body.clinician_id,
            duration_minutes=body.duration_minutes,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/queue",
    response_model=list[QueueEntryResponse],
    dependencies=[Depends(require(Capability.APPOINTMENT_READ))],
)
def read_queue(
    current_staff: CurrentStaff,
    branch_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """Who is being seen and who is waiting at one branch. Viewing it is noted in the diary."""
    try:
        return get_queue(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            branch_id=branch_id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.post(
    "/{appointment_id}/check-in",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def check_in_visit(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The patient has arrived and is now waiting."""
    return _change(check_in, session, current_staff.tenant_id, current_staff.id, appointment_id)


@router.post(
    "/{appointment_id}/start",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_CONSULT))],
)
def start_visit(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """A doctor or nurse starts the consultation."""
    return _change(
        start_consultation, session, current_staff.tenant_id, current_staff.id, appointment_id
    )


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_CONSULT))],
)
def complete_visit(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The clinician who started the consultation finishes it."""
    return _change(
        complete_consultation, session, current_staff.tenant_id, current_staff.id, appointment_id
    )


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def cancel_visit(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Cancel a visit that has not started. Its time becomes free again."""
    return _change(
        cancel_appointment, session, current_staff.tenant_id, current_staff.id, appointment_id
    )


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def no_show_visit(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The patient never came. Only allowed once the start time has passed."""
    return _change(
        mark_no_show, session, current_staff.tenant_id, current_staff.id, appointment_id
    )


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def reschedule_visit(
    appointment_id: uuid.UUID,
    body: RescheduleAppointment,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Move a booked visit to a new time."""
    try:
        return reschedule_appointment(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
            starts_at=body.starts_at,
            duration_minutes=body.duration_minutes,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None