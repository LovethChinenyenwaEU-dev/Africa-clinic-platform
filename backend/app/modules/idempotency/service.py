"""Remember the answer to a write, so sending it again changes nothing (FR-O3)."""
import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.modules.idempotency.models import IdempotencyRecord

# Long enough for a UUID or a timestamped key, short enough to index.
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
KEEP_FOR = timedelta(hours=24)
# Answers that must not be remembered: a retry should really run again.
NOT_REMEMBERED = {401, 408, 429}


class InvalidKeyError(ValueError):
    """The Idempotency-Key header is malformed."""


class KeyReusedError(Exception):
    """The same key was sent with a different request."""


def check_key(key: str) -> str:
    if not KEY_PATTERN.match(key):
        raise InvalidKeyError(
            "Idempotency-Key must be 8 to 100 letters, digits, '-' or '_'."
        )
    return key


def request_hash(method: str, path: str, query: str, body: bytes) -> str:
    """A fingerprint of the request: same key, different fingerprint is a client bug."""
    digest = hashlib.sha256()
    for part in (method.encode(), path.encode(), query.encode(), body):
        digest.update(len(part).to_bytes(8, "big"))  # keep the parts from blurring together
        digest.update(part)
    return digest.hexdigest()


def find_record(
    session: Session, *, tenant_id: uuid.UUID, staff_id: uuid.UUID, key: str, fingerprint: str
) -> IdempotencyRecord | None:
    """The remembered answer for this key, or None. Raises if the key was used differently."""
    statement = (
        select(IdempotencyRecord)
        .where(col(IdempotencyRecord.tenant_id) == tenant_id)
        .where(col(IdempotencyRecord.staff_id) == staff_id)
        .where(col(IdempotencyRecord.key) == key)
    )
    record = session.exec(statement).first()
    if record is not None and record.request_hash != fingerprint:
        raise KeyReusedError("This Idempotency-Key was already used for a different request.")
    return record


def should_remember(status_code: int) -> bool:
    return status_code < 500 and status_code not in NOT_REMEMBERED


def remember(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    key: str,
    fingerprint: str,
    status_code: int,
    response_body: str,
) -> None:
    """Keep the answer. If the same key was stored a moment ago by a parallel request,
    the first one wins and this one is quietly dropped."""
    session.add(
        IdempotencyRecord(
            tenant_id=tenant_id,
            staff_id=staff_id,
            key=key,
            request_hash=fingerprint,
            status_code=status_code,
            response_body=response_body,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def purge_old_records(session: Session, *, now: datetime | None = None) -> int:
    """Delete answers older than a day. Returns how many were deleted."""
    cutoff = (now or datetime.now(UTC)) - KEEP_FOR
    result = session.execute(
        delete(IdempotencyRecord).where(col(IdempotencyRecord.created_at) < cutoff)
    )
    session.commit()
    return result.rowcount or 0
