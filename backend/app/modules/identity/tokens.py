import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import DEFAULT_SECRET_KEY, settings

ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


class InvalidTokenError(Exception):
    """The token is missing, damaged, expired, or was not made by us."""


@dataclass(frozen=True)
class TokenClaims:
    """What is written on a valid wristband."""

    staff_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _signing_key() -> str:
    unsafe_default = settings.secret_key == DEFAULT_SECRET_KEY
    if unsafe_default and settings.environment not in ("development", "test"):
        raise RuntimeError("SECRET_KEY must be changed before running outside development.")
    return settings.secret_key


def create_access_token(
    *,
    staff_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    now: datetime | None = None,
    minutes: int = ACCESS_TOKEN_MINUTES,
) -> str:
    """Make a signed wristband. Only IDs and the role go on it, never secrets."""
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(staff_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, _signing_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    """Check the sticker and expiry, then read what is written on the token."""
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return TokenClaims(
            staff_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tenant_id"]),
            role=payload["role"],
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        raise InvalidTokenError("Invalid or expired token.") from None