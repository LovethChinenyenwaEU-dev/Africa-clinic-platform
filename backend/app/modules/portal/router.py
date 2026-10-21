"""Doors for the patient's own pages. Signing in is open on purpose; everything else
needs a patient token, and acts only on that patient's own record."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.consent.service import NoConsentTextError
from app.modules.identity.service import get_staff_in_tenant
from app.modules.portal.dependencies import CurrentPatient
from app.modules.portal.schemas import (
    BookRemoteVisit,
    ChatMessage,
    FinishSignIn,
    Me,
    MySummaryResponse,
    MyVisitResponse,
    PatientIntake,
    PatientIntakeAnswer,
    PatientMessage,
    PatientRoom,
    PatientToken,
    RemoteCareConsentResponse,
    RemoteSlotResponse,
    StartSignIn,
    StartSignInAnswer,
)
from app.modules.portal.selfservice import (
    AlreadyBookedError,
    SlotNotFreeError,
    agree_to_remote_care,
    answer_intake,
    book_remote_visit,
    join_room,
    read_chat,
    remote_care_consent,
    remote_slots,
    write_in_chat,
)
from app.modules.portal.signin import (
    CodeNotSentError,
    SignInFailedError,
    finish_sign_in,
    start_sign_in,
)
from app.modules.portal.views import my_summaries, my_visits
from app.modules.scheduling.lifecycle import AppointmentNotFoundError
from app.modules.scheduling.service import InvalidAppointmentError, SlotTakenError
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.telehealth.intake import (
    ESCALATION_ADVICE,
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
)
from app.modules.telehealth.readiness import IntakeOutcome
from app.modules.telehealth.room import ConsultNotLiveError, InvalidConsultError, RoomNotOpenError

router = APIRouter(prefix="/patient-portal", tags=["patient portal"])

SENT = (
    "If those details match a patient of this clinic, a code is on its way by SMS. "
    "It works for 10 minutes."
)


@router.post("/sign-in/start", response_model=StartSignInAnswer)
def begin_sign_in(body: StartSignIn, session: Session = Depends(get_session)):
    """Open on purpose. The same answer whether or not the details matched anyone."""
    try:
        result = start_sign_in(
            session,
            tenant_id=body.clinic_id,
            phone=body.phone,
            date_of_birth=body.date_of_birth,
        )
    except CodeNotSentError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None
    return StartSignInAnswer(message=SENT, development_code=result.development_code)


@router.post("/sign-in/finish", response_model=PatientToken)
def complete_sign_in(body: FinishSignIn, session: Session = Depends(get_session)):
    """Open on purpose. The right code gives a patient token for 30 minutes."""
    try:
        token = finish_sign_in(
            session,
            tenant_id=body.clinic_id,
            phone=body.phone,
            date_of_birth=body.date_of_birth,
            code=body.code,
        )
    except SignInFailedError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from None
    return PatientToken(access_token=token)


@router.get("/me", response_model=Me)
def read_me(patient: CurrentPatient):
    return patient


@router.get("/visits", response_model=list[MyVisitResponse])
def read_my_visits(patient: CurrentPatient, session: Session = Depends(get_session)):
    return my_visits(session, patient=patient)


@router.get("/summaries", response_model=list[MySummaryResponse])
def read_my_summaries(patient: CurrentPatient, session: Session = Depends(get_session)):
    return my_summaries(session, patient=patient)


# Remote care, done by the patient (Week 9 Step 8b)

SELF_SERVICE_ERRORS = (
    AppointmentNotFoundError,
    SlotNotFreeError,
    AlreadyBookedError,
    NoConsentTextError,
    InvalidAppointmentError,
    SlotTakenError,
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
    InvalidMoveError,
    InvalidConsultError,
    ConsultNotLiveError,
    RoomNotOpenError,
)


def _self_service_error(error: Exception) -> HTTPException:
    if isinstance(error, AppointmentNotFoundError):
        return HTTPException(status_code=404, detail="Visit not found.")
    if isinstance(error, InvalidAppointmentError | InvalidIntakeError | InvalidConsultError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, NoConsentTextError):
        return HTTPException(
            status_code=409, detail="The clinic has not published its wording for remote care yet."
        )
    return HTTPException(status_code=409, detail=str(error))


@router.get("/remote-care/consent", response_model=RemoteCareConsentResponse)
def read_remote_care_consent(patient: CurrentPatient, session: Session = Depends(get_session)):
    return remote_care_consent(session, patient=patient)


@router.post("/remote-care/consent", response_model=RemoteCareConsentResponse)
def agree_remote_care(patient: CurrentPatient, session: Session = Depends(get_session)):
    """The patient agrees to the clinic's current wording for remote care."""
    try:
        agree_to_remote_care(session, patient=patient)
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None
    return remote_care_consent(session, patient=patient)


@router.get("/remote-slots", response_model=list[RemoteSlotResponse])
def read_remote_slots(
    patient: CurrentPatient, from_day: date, session: Session = Depends(get_session)
):
    """Free remote slots of every clinician for a week from that Lagos day."""
    return remote_slots(session, patient=patient, from_day=from_day)


@router.post(
    "/visits", response_model=MyVisitResponse, status_code=status.HTTP_201_CREATED
)
def book_my_remote_visit(
    body: BookRemoteVisit, patient: CurrentPatient, session: Session = Depends(get_session)
):
    try:
        visit = book_remote_visit(
            session,
            patient=patient,
            clinician_id=body.clinician_id,
            starts_at=body.starts_at,
            appointment_id=body.id,
        )
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None
    clinician = get_staff_in_tenant(
        session, tenant_id=patient.tenant_id, staff_id=visit.clinician_id
    )
    return MyVisitResponse(
        appointment_id=visit.id,
        starts_at=visit.starts_at,
        ends_at=visit.ends_at,
        visit_type=visit.visit_type,
        status=visit.status,
        clinician_name=clinician.full_name if clinician else None,
    )


@router.post("/visits/{appointment_id}/intake", response_model=PatientIntakeAnswer)
def answer_my_intake(
    appointment_id: uuid.UUID,
    body: PatientIntake,
    patient: CurrentPatient,
    session: Session = Depends(get_session),
):
    """The reason and the danger-sign questions. A danger sign: go in person, now."""
    try:
        intake = answer_intake(
            session,
            patient=patient,
            appointment_id=appointment_id,
            reason=body.reason,
            red_flags=body.red_flags,
            intake_id=body.id,
        )
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None
    escalated = intake.outcome == IntakeOutcome.ESCALATED.value
    return PatientIntakeAnswer(
        outcome=intake.outcome, advice=ESCALATION_ADVICE if escalated else None
    )


@router.get("/visits/{appointment_id}/room", response_model=PatientRoom)
def join_my_room(
    appointment_id: uuid.UUID, patient: CurrentPatient, session: Session = Depends(get_session)
):
    try:
        mode, links = join_room(session, patient=patient, appointment_id=appointment_id)
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None
    return PatientRoom(mode=mode, video_url=links.video_url, audio_url=links.audio_url)


@router.get("/visits/{appointment_id}/messages", response_model=list[ChatMessage])
def read_my_chat(
    appointment_id: uuid.UUID,
    patient: CurrentPatient,
    since: datetime | None = None,
    session: Session = Depends(get_session),
):
    try:
        return read_chat(session, patient=patient, appointment_id=appointment_id, since=since)
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None


@router.post(
    "/visits/{appointment_id}/messages",
    response_model=ChatMessage,
    status_code=status.HTTP_201_CREATED,
)
def write_my_message(
    appointment_id: uuid.UUID,
    body: PatientMessage,
    patient: CurrentPatient,
    session: Session = Depends(get_session),
):
    try:
        return write_in_chat(
            session,
            patient=patient,
            appointment_id=appointment_id,
            body=body.body,
            message_id=body.id,
        )
    except SELF_SERVICE_ERRORS as error:
        raise _self_service_error(error) from None
