from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.core.db import get_session
from app.modules.outreach.service import Interest, TooManyRequestsError, submit_interest

router = APIRouter(prefix="/public", tags=["public"])


class InterestCreate(BaseModel):
    """The landing page's "Register interest" form. No patient information belongs here."""

    # Spaces around what was typed are dropped before the checks below (a pasted email).
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    organisation: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=60)
    message: str | None = Field(default=None, max_length=2000)


@router.post("/interest", status_code=status.HTTP_201_CREATED)
def register_interest(body: InterestCreate, session: Session = Depends(get_session)):
    """Public on purpose: anyone may register interest. Limited per email and per hour."""
    try:
        submit_interest(session, Interest(**body.model_dump()))
    except TooManyRequestsError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)
        ) from None
    return {"received": True}  # nothing about other requests, or this one, is sent back
