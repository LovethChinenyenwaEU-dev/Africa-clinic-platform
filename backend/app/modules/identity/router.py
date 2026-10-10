from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import get_current_staff
from app.modules.identity.models import Staff
from app.modules.identity.schemas import LoginRequest, MeResponse, TokenResponse
from app.modules.identity.service import InvalidCredentialsError, login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_endpoint(
    body: LoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    try:
        token = login(session, email=body.email, password=body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_staff: Staff = Depends(get_current_staff)) -> Staff:
    """Who am I? Needs a valid bearer token."""
    return current_staff
