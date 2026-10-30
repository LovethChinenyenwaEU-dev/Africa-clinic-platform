"""Signed-in devices (Week 11): end one device's sign-in without touching the others.

Each sign-in is a StaffSession row, and the access token carries its id. The staff door
(get_current_staff) checks on every request that the row is still open, so ending it
signs that device out at once: a copied or stolen token stops working, instead of
lasting its 30 minutes. Switching a person off still ends every device (is_active).

A person sees and ends their own devices; an admin can do it for anyone in the clinic.
"""
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.core.device import current_device_id
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.models import Staff, StaffSession
from app.modules.identity.tokens import ACCESS_TOKEN_MINUTES, TokenClaims, create_access_token

# last_seen_at is written at most this often, not on every click.
TOUCH_EVERY = timedelta(minutes=5)
MAX_LABEL_LENGTH = 120


class SessionNotFoundError(Exception):
    """No such open sign-in for this person in this clinic."""


@dataclass(frozen=True)
class DeviceView:
    session: StaffSession
    current: bool  # the device asking


_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"))
_SYSTEMS = (
    ("Android", "Android"),
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("Linux", "Linux"),
)


def describe_device(user_agent: str | None) -> str:
    """A short name a person recognises, from the browser's own description:
    "Chrome on Windows". Nothing more is kept from it."""
    agent = user_agent or ""
    browser = next((name for mark, name in _BROWSERS if mark in agent), None)
    if browser is None and "Safari/" in agent:
        browser = "Safari"
    system = next((name for mark, name in _SYSTEMS if mark in agent), None)
    if browser and system:
        return f"{browser} on {system}"
    if browser or system:
        return browser or system or "Unknown device"
    clean = re.sub(r"[^\w .;:/()-]", "", agent).strip()
    return clean[:MAX_LABEL_LENGTH] or "Unknown device"


def open_session(
    session: Session, *, staff: Staff, label: str | None = None, now: datetime | None = None
) -> str:
    """Record a new sign-in for this device and hand back its access token."""
    started = now or datetime.now(UTC)
    row = StaffSession(
        tenant_id=staff.tenant_id,
        staff_id=staff.id,
        device_id=current_device_id(),
        label=(label or "Unknown device")[:MAX_LABEL_LENGTH],
        created_at=started,
        last_seen_at=started,
        expires_at=started + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )
    session.add(row)
    session.commit()
    return create_access_token(
        staff_id=staff.id,
        tenant_id=staff.tenant_id,
        role=staff.role,
        now=started,
        session_id=row.id,
    )


def session_is_open(session: Session, claims: TokenClaims, now: datetime | None = None) -> bool:
    """Is this token's sign-in still open? Notes when the device was last seen."""
    if claims.session_id is None:
        return False  # every token is made with a sign-in since Week 11
    current = now or datetime.now(UTC)
    row = session.get(StaffSession, claims.session_id)
    if (
        row is None
        or row.staff_id != claims.staff_id
        or row.ended_at is not None
        or row.expires_at <= current
    ):
        return False
    if current - row.last_seen_at >= TOUCH_EVERY:
        row.last_seen_at = current
        session.add(row)
        session.commit()
    return True


def list_devices(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    current_session_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> list[DeviceView]:
    """The person's open sign-ins, newest first."""
    current = now or datetime.now(UTC)
    rows = session.exec(
        select(StaffSession)
        .where(col(StaffSession.tenant_id) == tenant_id)
        .where(col(StaffSession.staff_id) == staff_id)
        .where(col(StaffSession.ended_at).is_(None))
        .where(col(StaffSession.expires_at) > current)
        .order_by(col(StaffSession.created_at).desc())
    ).all()
    return [DeviceView(row, row.id == current_session_id) for row in rows]


def end_session(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    staff_id: uuid.UUID,
    session_id: uuid.UUID,
    now: datetime | None = None,
) -> StaffSession:
    """Sign one device out. Written in the diary, with who did it."""
    row = session.get(StaffSession, session_id)
    if (
        row is None
        or row.tenant_id != tenant_id
        or row.staff_id != staff_id
        or row.ended_at is not None
    ):
        raise SessionNotFoundError("Device not found.")
    row.ended_at = now or datetime.now(UTC)
    row.ended_by_id = actor_id
    session.add(row)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.SESSION_END,
        entity_id=row.id,
    )
    session.commit()
    session.refresh(row)
    return row


_INFO_KEY = "staff_session_id"


def remember_session_id(session: Session, session_id: uuid.UUID | None) -> None:
    """The staff door notes which sign-in this request belongs to."""
    session.info[_INFO_KEY] = session_id


def current_session_id(session: Session) -> uuid.UUID | None:
    """The sign-in of the request being handled (set by the staff door)."""
    return session.info.get(_INFO_KEY)
