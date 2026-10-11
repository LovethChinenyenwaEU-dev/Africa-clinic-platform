import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.consent.models import Consent, ConsentPurpose, ConsentText, GrantedBy
from app.modules.patients.service import PatientNotFoundError, patient_exists

MAX_CONSENT_TEXT_LENGTH = 5000


class InvalidConsentError(ValueError):
    """The consent details are not acceptable."""


class NoConsentTextError(Exception):
    """The clinic has not published any wording for this purpose yet."""


class ConsentNotFoundError(Exception):
    """There is no active consent to revoke."""


def _purpose(value: str) -> str:
    try:
        return ConsentPurpose(value).value
    except ValueError:
        raise InvalidConsentError(f"Unknown consent purpose: {value}") from None


def current_consent_text(
    session: Session, *, tenant_id: uuid.UUID, purpose: str
) -> ConsentText | None:
    """The newest wording this clinic has published for a purpose."""
    statement = (
        tenant_select(ConsentText, tenant_id)
        .where(col(ConsentText.purpose) == _purpose(purpose))
        .order_by(col(ConsentText.version).desc())
        .limit(1)
    )
    return session.exec(statement).first()


def publish_consent_text(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    purpose: str,
    body: str,
) -> ConsentText:
    """Publish new wording. It becomes the next version; old versions are kept forever."""
    purpose_value = _purpose(purpose)
    clean_body = body.strip()
    if not clean_body:
        raise InvalidConsentError("Consent text cannot be empty.")
    if len(clean_body) > MAX_CONSENT_TEXT_LENGTH:
        raise InvalidConsentError(
            f"Consent text must be at most {MAX_CONSENT_TEXT_LENGTH} characters."
        )

    latest = current_consent_text(session, tenant_id=tenant_id, purpose=purpose_value)
    text = ConsentText(
        tenant_id=tenant_id,
        purpose=purpose_value,
        version=latest.version + 1 if latest else 1,
        body=clean_body,
        created_by_id=actor_id,
    )
    session.add(text)
    session.commit()
    session.refresh(text)
    return text


def _active_consent(
    session: Session, *, tenant_id: uuid.UUID, patient_id: uuid.UUID, purpose_value: str
) -> Consent | None:
    statement = (
        tenant_select(Consent, tenant_id)
        .where(col(Consent.patient_id) == patient_id)
        .where(col(Consent.purpose) == purpose_value)
        .where(col(Consent.revoked_at).is_(None))
    )
    return session.exec(statement).first()


def has_active_consent(
    session: Session, *, tenant_id: uuid.UUID, patient_id: uuid.UUID, purpose: str
) -> bool:
    """The question every other feature asks before using a patient's information."""
    found = _active_consent(
        session, tenant_id=tenant_id, patient_id=patient_id, purpose_value=_purpose(purpose)
    )
    return found is not None


def grant_consent(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    purpose: str,
    granted_by: str,
) -> Consent:
    """Record that a patient agreed. Saved together with its diary line, or not at all."""
    purpose_value = _purpose(purpose)
    try:
        granted_by_value = GrantedBy(granted_by).value
    except ValueError:
        raise InvalidConsentError("granted_by must be patient or caregiver.") from None

    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise PatientNotFoundError("Patient not found.")

    existing = _active_consent(
        session, tenant_id=tenant_id, patient_id=patient_id, purpose_value=purpose_value
    )
    if existing is not None:
        return existing  # a double click changes nothing

    text = current_consent_text(session, tenant_id=tenant_id, purpose=purpose_value)
    if text is None:
        raise NoConsentTextError("No consent text has been published for this purpose.")

    consent = Consent(
        tenant_id=tenant_id,
        patient_id=patient_id,
        purpose=purpose_value,
        consent_text_id=text.id,
        granted_by=granted_by_value,
        recorded_by_id=actor_id,
    )
    session.add(consent)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.CONSENT_GRANT,
        patient_id=patient_id,
        purpose=purpose_value,
    )
    session.commit()
    session.refresh(consent)
    return consent


def revoke_consent(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    purpose: str,
) -> Consent:
    """Take permission back. The record stays, stamped with when and by whom."""
    purpose_value = _purpose(purpose)
    consent = _active_consent(
        session, tenant_id=tenant_id, patient_id=patient_id, purpose_value=purpose_value
    )
    if consent is None:
        raise ConsentNotFoundError("No active consent to revoke.")

    consent.revoked_at = datetime.now(UTC)
    consent.revoked_by_id = actor_id
    session.add(consent)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.CONSENT_REVOKE,
        patient_id=patient_id,
        purpose=purpose_value,
    )
    session.commit()
    session.refresh(consent)
    return consent