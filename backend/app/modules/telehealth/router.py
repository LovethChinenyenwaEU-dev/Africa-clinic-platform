"""Doors for remote visits (FR-C2, FR-C6).

Front desk, nurses and doctors take the intake (often on the phone). Only clinicians
read it back in full: the reason is health information.
"""
import uuid

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
from app.modules.telehealth.schemas import (
    IntakeForm,
    IntakeRecord,
    IntakeResponse,
    TeleconsultStatus,
)

router = APIRouter(prefix="/teleconsults", tags=["teleconsults"])

KNOWN_ERRORS = (
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
    AppointmentNotFoundError,
    InvalidMoveError,
)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidIntakeError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, AppointmentNotFoundError):
        return HTTPException(status_code=404, detail="Appointment not found.")
    if isinstance(error, NotATeleconsultError | TeleconsultConsentMissingError | InvalidMoveError):
        return HTTPException(status_code=409, detail=str(error))
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
