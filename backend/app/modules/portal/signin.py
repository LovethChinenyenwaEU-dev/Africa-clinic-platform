"""Patient sign-in with a one-time SMS code (Week 9 decision).

Start: the patient gives their phone number and date of birth. Both must match exactly
one patient of this clinic: families often share a phone, and the date of birth tells
them apart. Then a 6-digit code goes by SMS. The answer is the same whether or not
anyone matched, so nobody can find out who is registered.

Finish: the right code, within 10 minutes, once, in at most 5 tries, gives a patient
token for 30 minutes.

Only a keyed hash of the code is stored; the code itself is never stored or logged.
"""
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.tokens import create_patient_token
from app.modules.notifications.adapters import (
    MessageAdapter,
    OutgoingMessage,
    ProviderError,
    make_adapter,
)
from app.modules.patients.models import Patient
from app.modules.patients.phone import InvalidPhoneError, normalise_phone
from app.modules.portal.models import PatientLoginCode

CODE_MINUTES = 10
MAX_TRIES = 5
MAX_CODES = 3
CODES_WINDOW = timedelta(minutes=15)
PORTAL = "patient_portal"  # the audit purpose for everything a patient does themselves


class SignInFailedError(Exception):
    """Wrong, used, expired or worn-out code. One message for all, on purpose."""


class CodeNotSentError(Exception):
    """The SMS provider could not send the code right now."""


@dataclass(frozen=True)
class StartResult:
    # Only in development, where SMS is switched off: the code, so it can be tried out.
    development_code: str | None = None


def _hash(code_id: uuid.UUID, code: str) -> str:
    key = settings.secret_key.encode()
    return hmac.new(key, f"{code_id}:{code}".encode(), hashlib.sha256).hexdigest()


def sms_adapter() -> MessageAdapter:
    """The SMS door. Tests swap this for a fake that keeps what it was given."""
    return make_adapter(settings.sms_provider)


def _the_patient(
    session: Session, *, tenant_id: uuid.UUID, phone: str, date_of_birth: date
) -> Patient | None:
    """Exactly one patient with this phone and birth date, leaving out records found
    to be duplicates; otherwise None."""
    rows = session.exec(
        tenant_select(Patient, tenant_id)
        .where(col(Patient.phone) == phone)
        .where(col(Patient.date_of_birth) == date_of_birth)
    ).all()
    found = [row for row in rows if row.review_status != "duplicate"]
    return found[0] if len(found) == 1 else None


def start_sign_in(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    phone: str,
    date_of_birth: date,
    now: datetime | None = None,
) -> StartResult:
    """Send a code if the details match one patient. Says the same either way."""
    current = now or datetime.now(UTC)
    try:
        clean_phone = normalise_phone(phone)
    except InvalidPhoneError:
        return StartResult()
    patient = _the_patient(
        session, tenant_id=tenant_id, phone=clean_phone, date_of_birth=date_of_birth
    )
    if patient is None:
        return StartResult()

    recent = session.exec(
        select(func.count())
        .select_from(PatientLoginCode)
        .where(col(PatientLoginCode.tenant_id) == tenant_id)
        .where(col(PatientLoginCode.phone) == clean_phone)
        .where(col(PatientLoginCode.created_at) > current - CODES_WINDOW)
    ).one()
    if recent >= MAX_CODES:
        return StartResult()  # too many lately: quietly send nothing

    code = f"{secrets.randbelow(1_000_000):06d}"
    login = PatientLoginCode(
        tenant_id=tenant_id,
        patient_id=patient.id,
        phone=clean_phone,
        code_hash="",
        created_at=current,
        expires_at=current + timedelta(minutes=CODE_MINUTES),
    )
    login.code_hash = _hash(login.id, code)
    try:
        sms_adapter().send(
            OutgoingMessage(
                to=clean_phone,
                body=f"Your clinic sign-in code is {code}. It works for {CODE_MINUTES} minutes. "
                "Never share it, not even with clinic staff.",
            )
        )
    except ProviderError:
        raise CodeNotSentError("The code could not be sent. Please try again.") from None
    session.add(login)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=patient.id,
        action=AuditAction.PORTAL_CODE_SENT,
        patient_id=patient.id,
        purpose=PORTAL,
    )
    session.commit()
    return StartResult(development_code=code if settings.environment == "development" else None)


def finish_sign_in(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    phone: str,
    date_of_birth: date,
    code: str,
    now: datetime | None = None,
) -> str:
    """Check the newest code for these details; on success, a patient token."""
    current = now or datetime.now(UTC)
    try:
        clean_phone = normalise_phone(phone)
    except InvalidPhoneError:
        raise SignInFailedError("That code is not right, or has expired.") from None
    patient = _the_patient(
        session, tenant_id=tenant_id, phone=clean_phone, date_of_birth=date_of_birth
    )
    login = None
    if patient is not None:
        login = session.exec(
            tenant_select(PatientLoginCode, tenant_id)
            .where(col(PatientLoginCode.patient_id) == patient.id)
            .order_by(col(PatientLoginCode.created_at).desc())
            .with_for_update()
        ).first()
    usable = (
        login is not None
        and login.used_at is None
        and login.expires_at > current
        and login.attempts < MAX_TRIES
    )
    if not usable:
        raise SignInFailedError("That code is not right, or has expired.")

    login.attempts += 1
    if not hmac.compare_digest(login.code_hash, _hash(login.id, code.strip())):
        session.add(login)
        session.commit()  # the wrong try counts, even though the answer is "no"
        raise SignInFailedError("That code is not right, or has expired.")

    login.used_at = current
    session.add(login)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=patient.id,
        action=AuditAction.PORTAL_SIGN_IN,
        patient_id=patient.id,
        purpose=PORTAL,
    )
    session.commit()
    return create_patient_token(patient_id=patient.id, tenant_id=tenant_id, now=current)
