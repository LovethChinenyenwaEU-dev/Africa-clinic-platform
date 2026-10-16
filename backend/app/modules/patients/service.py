import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.models import Patient, ReviewStatus, Sex
from app.modules.patients.phone import InvalidPhoneError, normalise_phone

MIN_SEARCH_LENGTH = 2
MAX_SEARCH_RESULTS = 25
EARLIEST_BIRTH_DATE = date(1900, 1, 1)


class InvalidPatientError(ValueError):
    """The patient details are not acceptable."""
class PatientNotFoundError(Exception):
    """No patient with this ID in this clinic."""


@dataclass(frozen=True)
class DuplicateMatch:
    """A hint that someone may already be registered. IDs and a reason only, never names."""

    patient_id: uuid.UUID
    reason: str  # "same_phone" or "same_name_and_birth_date"


class PossibleDuplicateError(Exception):
    """A warning, not a failure: a human must decide whether this is a new person."""

    def __init__(self, matches: list[DuplicateMatch]) -> None:
        super().__init__("This patient may already be registered.")
        self.matches = matches


def find_possible_duplicates(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    full_name: str,
    date_of_birth: date,
    phone: str | None,
) -> list[DuplicateMatch]:
    """Look for people in THIS clinic who might be the same person."""
    found: dict[uuid.UUID, str] = {}

    if phone:
        same_phone = tenant_select(Patient, tenant_id).where(col(Patient.phone) == phone)
        for patient in session.exec(same_phone).all():
            found[patient.id] = "same_phone"

    same_person = (
        tenant_select(Patient, tenant_id)
        .where(func.lower(col(Patient.full_name)) == full_name.lower())
        .where(col(Patient.date_of_birth) == date_of_birth)
    )
    for patient in session.exec(same_person).all():
        found[patient.id] = "same_name_and_birth_date"  # the stronger reason wins

    return [DuplicateMatch(patient_id=pid, reason=reason) for pid, reason in found.items()]


def create_patient(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    full_name: str,
    date_of_birth: date,
    sex: str,
    phone: str | None = None,
    confirmed_not_duplicate: bool = False,
    patient_id: uuid.UUID | None = None,
    registered_offline: bool = False,
) -> Patient:
    """Register a patient. The patient and the diary line are saved together or not at all.

    patient_id may come from the device: sending the same one again changes nothing.
    registered_offline: the form was filled with no network, so nobody could answer
    the duplicate question. A possible duplicate is then saved anyway and flagged
    needs_review, rather than refused: the person is at the desk being seen.
    """
    if patient_id is not None:
        existing = get_in_tenant(session, Patient, tenant_id=tenant_id, row_id=patient_id)
        if isinstance(existing, Patient):
            return existing

    clean_name = " ".join(full_name.split())
    if not clean_name:
        raise InvalidPatientError("Patient name cannot be empty.")

    today = datetime.now(UTC).date()
    if date_of_birth > today or date_of_birth < EARLIEST_BIRTH_DATE:
        raise InvalidPatientError("Date of birth is not valid.")

    try:
        sex_value = Sex(sex).value
    except ValueError:
        raise InvalidPatientError("Sex must be female, male or other.") from None

    clean_phone = normalise_phone(phone) if phone and phone.strip() else None

    review_status = None
    if not confirmed_not_duplicate:
        matches = find_possible_duplicates(
            session,
            tenant_id=tenant_id,
            full_name=clean_name,
            date_of_birth=date_of_birth,
            phone=clean_phone,
        )
        if matches and not registered_offline:
            raise PossibleDuplicateError(matches)
        if matches:
            review_status = ReviewStatus.NEEDS_REVIEW.value

    patient = Patient(
        id=patient_id or uuid.uuid4(),
        tenant_id=tenant_id,
        full_name=clean_name,
        date_of_birth=date_of_birth,
        sex=sex_value,
        phone=clean_phone,
        created_by_id=actor_id,
        review_status=review_status,
    )
    session.add(patient)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PATIENT_CREATE,
        patient_id=patient.id,
    )
    session.commit()
    session.refresh(patient)
    return patient


def get_patient(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
) -> Patient | None:
    """One patient from this clinic. The diary line is saved before the data goes out."""
    row = get_in_tenant(session, Patient, tenant_id=tenant_id, row_id=patient_id)
    if not isinstance(row, Patient):
        return None

    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PATIENT_VIEW,
        patient_id=row.id,
    )
    session.commit()
    session.refresh(row)
    return row


def search_patients(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    query: str,
) -> list[Patient]:
    """Find patients in this clinic by phone number or part of a name."""
    text = " ".join(query.split())
    if len(text) < MIN_SEARCH_LENGTH:
        raise InvalidPatientError(f"Search needs at least {MIN_SEARCH_LENGTH} characters.")

    # The diary records THAT a search happened, never the words searched for.
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PATIENT_SEARCH,
    )
    session.commit()

    statement = tenant_select(Patient, tenant_id)
    try:
        statement = statement.where(col(Patient.phone) == normalise_phone(text))
    except InvalidPhoneError:
        statement = statement.where(col(Patient.full_name).icontains(text, autoescape=True))
    statement = statement.order_by(col(Patient.full_name)).limit(MAX_SEARCH_RESULTS)
    return list(session.exec(statement).all())
def patient_exists(session: Session, *, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
    """Yes or no. No personal information leaves, so no diary line is needed."""
    return get_in_tenant(session, Patient, tenant_id=tenant_id, row_id=patient_id) is not None


def get_reminder_phone(
    session: Session, *, tenant_id: uuid.UUID, patient_id: uuid.UUID
) -> str | None:
    """The phone number to send a reminder to, or None if the patient has none.

    Only the number leaves, nothing else about the patient. It does not write a
    diary line itself: the caller records the send, because that is the moment
    the number is handed to an outside provider.
    """
    row = get_in_tenant(session, Patient, tenant_id=tenant_id, row_id=patient_id)
    if not isinstance(row, Patient):
        return None
    return row.phone


def patient_names(
    session: Session, *, tenant_id: uuid.UUID, patient_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Full names only, in one query, for a list staff may already see (the queue).

    It writes no diary line itself: the screen that shows the list records the look.
    """
    if not patient_ids:
        return {}
    statement = tenant_select(Patient, tenant_id).where(col(Patient.id).in_(patient_ids))
    return {patient.id: patient.full_name for patient in session.exec(statement).all()}


# Reviewing registrations made offline (Week 8)


class NotWaitingForReviewError(Exception):
    """This patient is not waiting for a duplicate review (never was, or already decided)."""


@dataclass(frozen=True)
class ReviewItem:
    """A registration to review, with the people it may duplicate."""

    patient: Patient
    matches: list[tuple[Patient, str]]  # (possible original, reason)


def list_for_review(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID
) -> list[ReviewItem]:
    """This clinic's offline registrations waiting for a person to decide, oldest first.

    Names are shown so front desk can compare; looking at the list is in the diary.
    """
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.PATIENT_REVIEW_LIST
    )
    session.commit()

    waiting = session.exec(
        tenant_select(Patient, tenant_id)
        .where(col(Patient.review_status) == ReviewStatus.NEEDS_REVIEW.value)
        .order_by(col(Patient.created_at))
    ).all()
    items = []
    for patient in waiting:
        found = find_possible_duplicates(
            session,
            tenant_id=tenant_id,
            full_name=patient.full_name,
            date_of_birth=patient.date_of_birth,
            phone=patient.phone,
        )
        others = [match for match in found if match.patient_id != patient.id]
        rows = {
            row.id: row
            for row in session.exec(
                tenant_select(Patient, tenant_id).where(
                    col(Patient.id).in_([match.patient_id for match in others])
                )
            ).all()
        }
        items.append(
            ReviewItem(
                patient=patient,
                matches=[(rows[m.patient_id], m.reason) for m in others if m.patient_id in rows],
            )
        )
    return items


def review_patient(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    duplicate_of: uuid.UUID | None,
) -> Patient:
    """Decide on an offline registration: someone new (duplicate_of None), or already
    registered as duplicate_of. Nothing is merged or deleted; visits already made under
    this record stay on it, and staff use the original from now on."""
    statement = (
        tenant_select(Patient, tenant_id).where(col(Patient.id) == patient_id).with_for_update()
    )
    patient = session.exec(statement).first()
    if patient is None:
        raise PatientNotFoundError("Patient not found.")
    if patient.review_status != ReviewStatus.NEEDS_REVIEW.value:
        raise NotWaitingForReviewError("This registration is not waiting for review.")

    if duplicate_of is None:
        patient.review_status = ReviewStatus.CONFIRMED_NEW.value
    else:
        if duplicate_of == patient.id:
            raise InvalidPatientError("A patient cannot be a duplicate of themselves.")
        if not patient_exists(session, tenant_id=tenant_id, patient_id=duplicate_of):
            raise PatientNotFoundError("Patient not found.")
        patient.review_status = ReviewStatus.DUPLICATE.value
        patient.duplicate_of_id = duplicate_of

    session.add(patient)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PATIENT_REVIEW,
        patient_id=patient.id,
    )
    session.commit()
    session.refresh(patient)
    return patient
