"""Signing in with an authenticator app (Week 11, SRS FR-T4).

Admins (staff, prices, refunds, the audit log) and billing (all the clinic's money) must
use a second factor. Everyone else signs in with a password, so a busy clinic is not
slowed down.

1. The right password gives these roles a 5-minute challenge, not an access token.
2. The first time, they set up their app: we make a secret, they add it to their app
   (scan or type), and prove it with a first code. They then get 10 backup codes, shown
   once, for a lost phone.
3. Each time after, they type the code their app shows (or one backup code).

No code works twice. Five wrong codes in a row lock sign-in for 15 minutes. An admin can
reset another person's app (lost phone): that person sets it up again.

The secret is kept as text in the database for now; encrypting it with a managed key
comes with deployment (W12). Backup codes are kept only as keyed hashes.
"""
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.config import settings
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity import totp
from app.modules.identity.models import Role, Staff, StaffBackupCode, StaffMfa
from app.modules.identity.service import StaffNotFoundError, authenticate, get_staff_in_tenant
from app.modules.identity.sessions import open_session
from app.modules.identity.tokens import (
    InvalidTokenError,
    create_challenge_token,
    decode_challenge_token,
)

MFA_ROLES = frozenset({Role.ADMIN.value, Role.BILLING.value})
MAX_FAILED_CODES = 5
LOCK_MINUTES = 15
BACKUP_CODE_COUNT = 10
_BACKUP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread


class ChallengeError(Exception):
    """The sign-in challenge is missing, expired or not for this step."""


class WrongCodeError(Exception):
    """The code is not right (or was already used)."""


class LockedError(Exception):
    """Too many wrong codes: wait before trying again."""


class AlreadySetUpError(Exception):
    """This person's app is already set up; use it to sign in."""


class OwnResetError(Exception):
    """Nobody resets their own app: another admin must do it."""


@dataclass(frozen=True)
class SignInStep:
    """After the password: either the access token, or the next step and its challenge."""

    access_token: str | None = None
    mfa: str | None = None  # "setup" (first time) or "verify"
    challenge_token: str | None = None


@dataclass(frozen=True)
class SetUp:
    secret: str
    otpauth_uri: str


@dataclass(frozen=True)
class Confirmed:
    access_token: str
    backup_codes: list[str]


def needs_mfa(staff: Staff) -> bool:
    return staff.role in MFA_ROLES


def _token(session: Session, staff: Staff, label: str | None) -> str:
    return open_session(session, staff=staff, label=label)


def _hash_backup(code: str) -> str:
    clean = code.strip().upper().replace("-", "").replace(" ", "")
    return hmac.new(settings.secret_key.encode(), clean.encode(), hashlib.sha256).hexdigest()


def _new_backup_code() -> str:
    raw = "".join(secrets.choice(_BACKUP_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _mfa_row(session: Session, staff_id: uuid.UUID, lock: bool = False) -> StaffMfa | None:
    statement = select(StaffMfa).where(col(StaffMfa.staff_id) == staff_id)
    if lock:
        statement = statement.with_for_update()
    return session.exec(statement).first()


def _audit(session: Session, staff: Staff, action: AuditAction) -> None:
    add_audit_event(
        session, tenant_id=staff.tenant_id, actor_id=staff.id, action=action, entity_id=staff.id
    )


def start_sign_in(
    session: Session, *, email: str, password: str, label: str | None = None
) -> SignInStep:
    """The password step. Raises InvalidCredentialsError for a wrong password."""
    staff = authenticate(session, email=email, password=password)
    if not needs_mfa(staff):
        return SignInStep(access_token=_token(session, staff, label))
    row = _mfa_row(session, staff.id)
    step = "verify" if row is not None and row.confirmed_at is not None else "setup"
    challenge = create_challenge_token(staff_id=staff.id, tenant_id=staff.tenant_id)
    return SignInStep(mfa=step, challenge_token=challenge)


def _staff_for(session: Session, challenge_token: str) -> Staff:
    try:
        claims = decode_challenge_token(challenge_token)
    except InvalidTokenError:
        raise ChallengeError("Sign in again: this step has expired.") from None
    staff = get_staff_in_tenant(session, tenant_id=claims.tenant_id, staff_id=claims.staff_id)
    if staff is None or not staff.is_active:
        raise ChallengeError("Sign in again: this step has expired.")
    return staff


def _check_lock(session: Session, row: StaffMfa, now: datetime) -> None:
    if row.locked_until is not None and row.locked_until > now:
        session.rollback()
        raise LockedError(f"Too many wrong codes. Try again in {LOCK_MINUTES} minutes.")


def _wrong(session: Session, staff: Staff, row: StaffMfa, now: datetime) -> NoReturn:
    row.failed_attempts += 1
    if row.failed_attempts >= MAX_FAILED_CODES:
        row.locked_until = now + timedelta(minutes=LOCK_MINUTES)
        row.failed_attempts = 0
    session.add(row)
    _audit(session, staff, AuditAction.MFA_FAIL)
    session.commit()
    raise WrongCodeError("That code is not right. Check your app and try again.")


def begin_setup(session: Session, *, challenge_token: str) -> SetUp:
    """A new secret for the person's app. Asking again replaces a secret not yet proved."""
    staff = _staff_for(session, challenge_token)
    row = _mfa_row(session, staff.id, lock=True)
    if row is not None and row.confirmed_at is not None:
        session.rollback()
        raise AlreadySetUpError("Your app is already set up. Sign in with its code.")
    secret = totp.new_secret()
    if row is None:
        row = StaffMfa(staff_id=staff.id, tenant_id=staff.tenant_id, secret=secret)
    else:
        row.secret = secret
        row.failed_attempts = 0
    session.add(row)
    session.commit()
    return SetUp(secret=secret, otpauth_uri=totp.provisioning_uri(secret, staff.email))


def confirm_setup(
    session: Session,
    *,
    challenge_token: str,
    code: str,
    now: datetime | None = None,
    label: str | None = None,
) -> Confirmed:
    """The first code proves the app works. Answers the access token and the backup codes."""
    current = now or datetime.now(UTC)
    staff = _staff_for(session, challenge_token)
    row = _mfa_row(session, staff.id, lock=True)
    if row is None:
        session.rollback()
        raise ChallengeError("Start the set-up first.")
    if row.confirmed_at is not None:
        session.rollback()
        raise AlreadySetUpError("Your app is already set up. Sign in with its code.")
    _check_lock(session, row, current)
    step = totp.matching_step(row.secret, code, current.timestamp(), row.last_step)
    if step is None:
        _wrong(session, staff, row, current)

    codes = [_new_backup_code() for _ in range(BACKUP_CODE_COUNT)]
    session.execute(delete(StaffBackupCode).where(col(StaffBackupCode.staff_id) == staff.id))
    for code_text in codes:
        session.add(
            StaffBackupCode(
                tenant_id=staff.tenant_id, staff_id=staff.id, code_hash=_hash_backup(code_text)
            )
        )
    row.confirmed_at = current
    row.last_step = step
    row.failed_attempts = 0
    row.locked_until = None
    session.add(row)
    _audit(session, staff, AuditAction.MFA_ENROLL)
    session.commit()
    return Confirmed(access_token=_token(session, staff, label), backup_codes=codes)


def verify_sign_in(
    session: Session,
    *,
    challenge_token: str,
    code: str,
    now: datetime | None = None,
    label: str | None = None,
) -> str:
    """The code from the app, or one backup code. Answers the access token."""
    current = now or datetime.now(UTC)
    staff = _staff_for(session, challenge_token)
    row = _mfa_row(session, staff.id, lock=True)
    if row is None or row.confirmed_at is None:
        session.rollback()
        raise ChallengeError("Set up your app first.")
    _check_lock(session, row, current)

    step = totp.matching_step(row.secret, code, current.timestamp(), row.last_step)
    if step is not None:
        row.last_step = step
        action = AuditAction.MFA_VERIFY
    else:
        backup = session.exec(
            select(StaffBackupCode)
            .where(col(StaffBackupCode.staff_id) == staff.id)
            .where(col(StaffBackupCode.code_hash) == _hash_backup(code))
            .where(col(StaffBackupCode.used_at).is_(None))
            .with_for_update()
        ).first()
        if backup is None:
            _wrong(session, staff, row, current)
        backup.used_at = current
        session.add(backup)
        action = AuditAction.MFA_BACKUP_USED

    row.failed_attempts = 0
    row.locked_until = None
    session.add(row)
    _audit(session, staff, action)
    session.commit()
    return _token(session, staff, label)


def reset_mfa(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, staff_id: uuid.UUID
) -> None:
    """An admin clears another person's app (lost phone). They set it up again next time."""
    if staff_id == actor_id:
        raise OwnResetError("Another admin must reset your app.")
    staff = get_staff_in_tenant(session, tenant_id=tenant_id, staff_id=staff_id)
    if staff is None:
        raise StaffNotFoundError("Staff member not found.")
    session.execute(delete(StaffBackupCode).where(col(StaffBackupCode.staff_id) == staff.id))
    session.execute(delete(StaffMfa).where(col(StaffMfa.staff_id) == staff.id))
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.MFA_RESET,
        entity_id=staff.id,
    )
    session.commit()
