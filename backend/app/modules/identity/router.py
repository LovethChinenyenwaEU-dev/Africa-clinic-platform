from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.schemas import LoginRequest, TokenResponse
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