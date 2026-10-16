"""Doors for remote visits (FR-C2, FR-C6).

Front desk, nurses and doctors take the intake (often on the phone). Only clinicians
read it back in full: the reason is health information.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.scheduling.lifecycle import AppointmentNotFoundError
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.telehealth.intake import (
    ESCALATION_ADVICE,
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
    intake_history,
    submit_intake,
    teleconsult_status,
)
from app.modules.telehealth.readiness import IntakeOutcome
from app.modules.telehealth.room import (
    ConsultNotLiveError,
    InvalidConsultError,
    NotTheConsultingClinicianError,
    RoomNotOpenError,
    change_mode,
    find_room,
    list_messages,
    mode_history,
    open_room,
    room_links,
    send_message,
)
from app.modules.telehealth.schemas import (
    ChangeMode,
    IntakeForm,
    IntakeRecord,
    IntakeResponse,
    MessageResponse,
    ModeChangeResponse,
    RoomResponse,
    SendMessage,
    TeleconsultStatus,
)

router = APIRouter(prefix="/teleconsults", tags=["teleconsults"])

KNOWN_ERRORS = (
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
    AppointmentNotFoundError,
    InvalidMoveError,
    ConsultNotLiveError,
    InvalidConsultError,
    NotTheConsultingClinicianError,
    RoomNotOpenError,
)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidIntakeError | InvalidConsultError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, AppointmentNotFoundError):
        return HTTPException(status_code=404, detail="Appointment not found.")
    if isinstance(
        error,
        NotATeleconsultError
        | TeleconsultConsentMissingError
        | InvalidMoveError
        | ConsultNotLiveError
        | RoomNotOpenError,
    ):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, NotTheConsultingClinicianError):
        return HTTPException(status_code=403, detail=str(error))
    raise error


def _with_advice(model: type[IntakeResponse], intake) -> IntakeResponse:
    answer = model.model_validate(intake)
    if intake.outcome == IntakeOutcome.ESCALATED.value:
        answer.advice = ESCALATION_ADVICE
    return answer


@router.post(
    "/{appointment_id}/intake",
    response_model=IntakeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.APPOINTMENT_WRITE))],
)
def take_intake(
    appointment_id: uuid.UUID,
    body: IntakeForm,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Reason and danger signs. No danger sign: the patient joins the remote waiting room.
    A danger sign: in-person care is advised, and the remote visit cannot start."""
    try:
        intake = submit_intake(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
            reason=body.reason,
            red_flags=body.red_flags,
            intake_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
    return _with_advice(IntakeResponse, intake)


@router.get(
    "/{appointment_id}/intake",
    response_model=list[IntakeRecord],
    dependencies=[Depends(require(Capability.CLINICAL_READ))],
)
def read_intake(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Every intake of this remote visit, newest first, with the patient's reason."""
    try:
        rows = intake_history(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
    return [_with_advice(IntakeRecord, row) for row in rows]


@router.get(
    "/{appointment_id}/status",
    response_model=TeleconsultStatus,
    dependencies=[Depends(require(Capability.APPOINTMENT_READ))],
)
def read_status(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Has the patient consented to remote care, and what did the intake decide?"""
    try:
        consented, outcome = teleconsult_status(
            session, tenant_id=current_staff.tenant_id, appointment_id=appointment_id
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
    return TeleconsultStatus(consented=consented, intake=outcome)


# The consult room (FR-C3, FR-C4): the clinician running the visit opens it, switches
# between video, audio and text, and chats. Clinicians may read the chat afterwards.

CONSULT = [Depends(require(Capability.APPOINTMENT_CONSULT))]
READ_RECORD = [Depends(require(Capability.CLINICAL_READ))]


def _room_answer(room) -> RoomResponse:
    links = room_links(room)
    return RoomResponse(
        appointment_id=room.appointment_id,
        provider=room.provider,
        mode=room.mode,
        video_url=links.video_url,
        audio_url=links.audio_url,
    )


@router.post("/{appointment_id}/room", response_model=RoomResponse, dependencies=CONSULT)
def open_consult_room(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Open the room of a remote visit in progress. Opening it again gives the same room."""
    try:
        room = open_room(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
    return _room_answer(room)


@router.get("/{appointment_id}/room", response_model=RoomResponse, dependencies=READ_RECORD)
def read_consult_room(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    room = find_room(session, tenant_id=current_staff.tenant_id, appointment_id=appointment_id)
    if room is None:
        raise HTTPException(status_code=404, detail="The room has not been opened.")
    return _room_answer(room)


@router.post("/{appointment_id}/mode", response_model=RoomResponse, dependencies=CONSULT)
def switch_mode(
    appointment_id: uuid.UUID,
    body: ChangeMode,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Video, audio or text, and why. Each switch is recorded."""
    try:
        room = change_mode(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
            to_mode=body.mode,
            reason=body.reason,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
    return _room_answer(room)


@router.get(
    "/{appointment_id}/mode-changes",
    response_model=list[ModeChangeResponse],
    dependencies=READ_RECORD,
)
def read_mode_changes(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    return mode_history(session, tenant_id=current_staff.tenant_id, appointment_id=appointment_id)


@router.post(
    "/{appointment_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=CONSULT,
)
def write_message(
    appointment_id: uuid.UUID,
    body: SendMessage,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    try:
        return send_message(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
            body=body.body,
            message_id=body.id,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None


@router.get(
    "/{appointment_id}/messages", response_model=list[MessageResponse], dependencies=READ_RECORD
)
def read_messages(
    appointment_id: uuid.UUID,
    current_staff: CurrentStaff,
    since: datetime | None = None,
    session: Session = Depends(get_session),
):
    """The chat. With `since`, only messages sent at or after it (small, for weak networks)."""
    try:
        return list_messages(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            appointment_id=appointment_id,
            since=since,
        )
    except KNOWN_ERRORS as error:
        raise _http_error(error) from None
