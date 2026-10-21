"""Doors for the patient's own pages. Signing in is open on purpose; everything else
needs a patient token, and acts only on that patient's own record."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.portal.dependencies import CurrentPatient
from app.modules.portal.schemas import (
    FinishSignIn,
    Me,
    MySummaryResponse,
    MyVisitResponse,
    PatientToken,
    StartSignIn,
    StartSignInAnswer,
)
from app.modules.portal.signin import (
    CodeNotSentError,
    SignInFailedError,
    finish_sign_in,
    start_sign_in,
)
from app.modules.portal.views import my_summaries, my_visits

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
