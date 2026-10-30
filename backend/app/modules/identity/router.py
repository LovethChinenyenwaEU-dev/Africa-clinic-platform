from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import get_current_staff
from app.modules.identity.mfa import (
    AlreadySetUpError,
    ChallengeError,
    LockedError,
    WrongCodeError,
    begin_setup,
    confirm_setup,
    start_sign_in,
    verify_sign_in,
)
from app.modules.identity.models import Staff
from app.modules.identity.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    MfaChallenge,
    MfaCode,
    MfaConfirmedResponse,
    MfaSetupResponse,
    TokenResponse,
)
from app.modules.identity.service import InvalidCredentialsError
from app.modules.identity.sessions import (
    SessionNotFoundError,
    current_session_id,
    describe_device,
    end_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _label(request: Request) -> str:
    """A name the person will recognise in their device list, such as "Chrome on Windows"."""
    return describe_device(request.headers.get("user-agent"))


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
def login_endpoint(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """The password step. Most staff get their token here; admins and billing get the
    second-factor step (mfa and challenge_token) instead."""
    try:
        step = start_sign_in(
            session, email=body.email, password=body.password, label=_label(request)
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return LoginResponse(
        access_token=step.access_token, mfa=step.mfa, challenge_token=step.challenge_token
    )


def _mfa_error(error: Exception) -> HTTPException:
    if isinstance(error, ChallengeError | WrongCodeError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    if isinstance(error, LockedError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error))
    if isinstance(error, AlreadySetUpError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    raise error


MFA_ERRORS = (ChallengeError, WrongCodeError, LockedError, AlreadySetUpError)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(body: MfaChallenge, session: Session = Depends(get_session)):
    """First time: a secret to add to the authenticator app (type it, or open the link)."""
    try:
        result = begin_setup(session, challenge_token=body.challenge_token)
    except MFA_ERRORS as error:
        raise _mfa_error(error) from None
    return MfaSetupResponse(secret=result.secret, otpauth_uri=result.otpauth_uri)


@router.post("/mfa/confirm", response_model=MfaConfirmedResponse)
def mfa_confirm(body: MfaCode, request: Request, session: Session = Depends(get_session)):
    """The first code proves the app works: signed in, with 10 backup codes shown once."""
    try:
        result = confirm_setup(
            session,
            challenge_token=body.challenge_token,
            code=body.code,
            label=_label(request),
        )
    except MFA_ERRORS as error:
        raise _mfa_error(error) from None
    return MfaConfirmedResponse(access_token=result.access_token, backup_codes=result.backup_codes)


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(body: MfaCode, request: Request, session: Session = Depends(get_session)):
    """The code from the app (or a backup code): signed in."""
    try:
        token = verify_sign_in(
            session,
            challenge_token=body.challenge_token,
            code=body.code,
            label=_label(request),
        )
    except MFA_ERRORS as error:
        raise _mfa_error(error) from None
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_staff: Staff = Depends(get_current_staff)) -> Staff:
    """Who am I? Needs a valid bearer token."""
    return current_staff


@router.post("/logout")
def logout(
    current_staff: Staff = Depends(get_current_staff),
    session: Session = Depends(get_session),
):
    """Sign this device out: its token stops working at once, not after 30 minutes."""
    session_id = current_session_id(session)
    if session_id is not None:
        try:
            end_session(
                session,
                tenant_id=current_staff.tenant_id,
                actor_id=current_staff.id,
                staff_id=current_staff.id,
                session_id=session_id,
            )
        except SessionNotFoundError:
            pass  # already ended: signing out twice is fine
    return {"signed_out": True}
