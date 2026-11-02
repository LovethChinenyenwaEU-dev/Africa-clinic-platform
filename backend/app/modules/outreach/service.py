"""Saving and reading "Register interest" requests.

The form is public, so it is limited: one email address may send 3 requests a day, and
the whole form takes at most 100 an hour. Beyond that it answers "too many" and saves
nothing. Old requests are deleted after a year (the worker calls purge_old_interest).
"""
import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from app.modules.outreach.models import InterestRequest

PER_EMAIL_PER_DAY = 3
PER_HOUR = 100
KEEP_FOR = timedelta(days=365)


class TooManyRequestsError(Exception):
    """The limit for this email address, or for the form as a whole, was reached."""


@dataclass(frozen=True)
class Interest:
    full_name: str
    email: str
    organisation: str
    role: str
    phone: str | None = None
    message: str | None = None


def _clean(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return text or None


def _count_since(session: Session, since: datetime, email: str | None = None) -> int:
    statement = select(func.count()).select_from(InterestRequest).where(
        col(InterestRequest.created_at) >= since
    )
    if email is not None:
        statement = statement.where(col(InterestRequest.email) == email)
    return int(session.exec(statement).one())


def submit_interest(
    session: Session, interest: Interest, *, now: datetime | None = None
) -> InterestRequest:
    """Save one request, unless a limit is reached."""
    current = now or datetime.now(UTC)
    email = interest.email.strip().lower()
    if _count_since(session, current - timedelta(days=1), email) >= PER_EMAIL_PER_DAY:
        raise TooManyRequestsError("You have already sent this a few times today.")
    if _count_since(session, current - timedelta(hours=1)) >= PER_HOUR:
        raise TooManyRequestsError("Too many requests just now. Please try again later.")
    row = InterestRequest(
        full_name=_clean(interest.full_name) or "",
        email=email,
        phone=_clean(interest.phone),
        organisation=_clean(interest.organisation) or "",
        role=_clean(interest.role) or "",
        message=(interest.message or "").strip() or None,
        created_at=current,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def interest_csv(session: Session, *, since: datetime) -> str:
    """Requests since a moment, newest first, as CSV for the platform owner."""
    rows = session.exec(
        select(InterestRequest)
        .where(col(InterestRequest.created_at) >= since)
        .order_by(col(InterestRequest.created_at).desc())
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["received", "name", "email", "phone", "organisation", "role", "message"])
    for row in rows:
        writer.writerow(
            [
                row.created_at.isoformat(timespec="minutes"),
                row.full_name,
                row.email,
                row.phone or "",
                row.organisation,
                row.role,
                row.message or "",
            ]
        )
    return out.getvalue()


def purge_old_interest(session: Session, *, now: datetime | None = None) -> int:
    """Delete requests older than a year. Returns how many were deleted."""
    cutoff = (now or datetime.now(UTC)) - KEEP_FOR
    result = session.execute(
        delete(InterestRequest).where(col(InterestRequest.created_at) < cutoff)
    )
    session.commit()
    return result.rowcount or 0
