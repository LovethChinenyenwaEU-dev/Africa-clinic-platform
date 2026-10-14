"""Public door of the records module: encounters.

Every function writes its diary line in the same transaction as the change,
and every read of a patient's encounters is itself written in the diary.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_clinician
from app.modules.patients.service import PatientNotFoundError, patient_exists
from app.modules.records.models import Encounter
from app.modules.records.statuses import ALLOWED_MOVES, EncounterStatus
from app.modules.scheduling.service import get_appointment

# A visit can have its encounter opened at triage (waiting) or during the consultation.
OPENABLE_VISIT_STATUSES = frozenset({"waiting", "in_consult"})
MAX_HISTORY = 100


class NotAClinicianError(Exception):
    """Only an active doctor or nurse of this clinic may do this."""


class EncounterNotFoundError(Exception):
    """No encounter with this ID in this clinic."""


class VisitNotFoundError(Exception):
    """No visit with this ID in this clinic."""


class VisitMismatchError(Exception):
    """The visit is for another patient, or not at a stage where an encounter can start."""


class InvalidEncounterMoveError(Exception):
    """The encounter cannot move from its current status to that one."""


class NotEncounterOwnerError(Exception):
    """Only the clinician who opened the encounter may sign it off."""


class EncounterNotOpenError(Exception):
    """New clinical entries can only go into an open encounter."""


class NotCurrentVersionError(Exception):
    """Only the newest version can be changed; this one was already replaced."""


def _require_clinician(session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    if not is_active_clinician(session, tenant_id=tenant_id, staff_id=actor_id):
        raise NotAClinicianError("Only an active doctor or nurse can do this.")


def _existing_for(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    encounter_id: uuid.UUID | None,
    appointment_id: uuid.UUID | None,
) -> Encounter | None:
    """An encounter this request already created: same device ID, or same visit."""
    if encounter_id is not None:
        found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
        if isinstance(found, Encounter):
            return found
    if appointment_id is not None:
        statement = tenant_select(Encounter, tenant_id).where(
            col(Encounter.appointment_id) == appointment_id
        )
        return session.exec(statement).first()
    return None


def open_encounter(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    appointment_id: uuid.UUID | None = None,
    encounter_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Encounter:
    """Start recording for a patient. Sending the same request again returns the same encounter.

    encounter_id may be made by the device, so an encounter saved offline keeps its ID.
    """
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise PatientNotFoundError("Patient not found.")

    if appointment_id is not None:
        visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
        if visit is None:
            raise VisitNotFoundError("Visit not found.")
        if visit.patient_id != patient_id:
            raise VisitMismatchError("That visit is for a different patient.")
        if visit.status not in OPENABLE_VISIT_STATUSES:
            raise VisitMismatchError("An encounter can only start once the patient has arrived.")

    existing = _existing_for(
        session, tenant_id=tenant_id, encounter_id=encounter_id, appointment_id=appointment_id
    )
    if existing is not None:
        return existing  # a retry or a double tap changes nothing

    encounter = Encounter(
        id=encounter_id or uuid.uuid4(),
        tenant_id=tenant_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        clinician_id=actor_id,
        status=EncounterStatus.OPEN.value,
        opened_at=current,
    )
    session.add(encounter)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.ENCOUNTER_CREATE,
        patient_id=patient_id,
        entity_id=encounter.id,
    )
    try:
        session.commit()
    except IntegrityError:
        # Two taps arrived at the same moment and the other one won. Return its encounter.
        session.rollback()
        winner = _existing_for(
            session, tenant_id=tenant_id, encounter_id=encounter_id, appointment_id=appointment_id
        )
        if winner is None:
            raise
        return winner
    session.refresh(encounter)
    return encounter


def _load_locked(
    session: Session, *, tenant_id: uuid.UUID, encounter_id: uuid.UUID
) -> Encounter:
    statement = (
        tenant_select(Encounter, tenant_id)
        .where(col(Encounter.id) == encounter_id)
        .with_for_update()
    )
    encounter = session.exec(statement).first()
    if encounter is None:
        raise EncounterNotFoundError("Encounter not found.")
    return encounter


def _move(encounter: Encounter, target: EncounterStatus) -> None:
    current = EncounterStatus(encounter.status)
    if target not in ALLOWED_MOVES[current]:
        raise InvalidEncounterMoveError(
            f"An encounter that is {current.value} cannot become {target.value}."
        )
    encounter.status = target.value


def _change_status(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    target: EncounterStatus,
    action: AuditAction,
    now: datetime | None,
) -> Encounter:
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    encounter = _load_locked(session, tenant_id=tenant_id, encounter_id=encounter_id)
    # One clinician answers for each encounter from start to sign-off.
    if encounter.clinician_id != actor_id:
        raise NotEncounterOwnerError("Only the clinician who opened this encounter can do this.")
    _move(encounter, target)
    encounter.closed_at = current
    encounter.closed_by_id = actor_id
    session.add(encounter)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    session.refresh(encounter)
    return encounter


def close_encounter(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    now: datetime | None = None,
) -> Encounter:
    """Sign off. Only the clinician who opened the encounter may close it."""
    return _change_status(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        encounter_id=encounter_id,
        target=EncounterStatus.CLOSED,
        action=AuditAction.ENCOUNTER_CLOSE,
        now=now,
    )


def mark_entered_in_error(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    now: datetime | None = None,
) -> Encounter:
    """The encounter was opened by mistake. It is kept and marked, never deleted.
    Only the clinician who opened it may say so."""
    return _change_status(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        encounter_id=encounter_id,
        target=EncounterStatus.ENTERED_IN_ERROR,
        action=AuditAction.ENCOUNTER_ENTERED_IN_ERROR,
        now=now,
    )


def get_encounter(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
) -> Encounter | None:
    """One encounter of this clinic. The diary line is saved before the data goes out."""
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        return None
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.ENCOUNTER_VIEW,
        patient_id=found.patient_id,
        entity_id=found.id,
    )
    session.commit()
    session.refresh(found)
    return found


def list_patient_encounters(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    limit: int = 50,
) -> list[Encounter]:
    """A patient's encounters in this clinic, newest first. Reading the list is logged."""
    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise PatientNotFoundError("Patient not found.")
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.ENCOUNTER_LIST,
        patient_id=patient_id,
    )
    session.commit()
    statement = (
        tenant_select(Encounter, tenant_id)
        .where(col(Encounter.patient_id) == patient_id)
        .order_by(col(Encounter.opened_at).desc())
        .limit(min(limit, MAX_HISTORY))
    )
    return list(session.exec(statement).all())
