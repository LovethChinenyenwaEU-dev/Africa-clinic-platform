"""Prescriptions: write, change and read (FR-R2). Doctors only.

A prescription is written inside an encounter, like vitals and notes, and follows
the same offline rules: the device makes its ID (a re-send changes nothing), one
written offline before sign-off is accepted after it and marked synced_late, and
two devices changing the same one keep both versions as a conflict.

Stopping or fixing a prescription is a new version, also after sign-off: a doctor
may stop a medicine days later. The old version is kept.

What the doctor types is health information: never put in logs or error messages.
"""
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_prescriber
from app.modules.records.conflicts import SHOWN, new_version_status, resolve_conflict
from app.modules.records.late import CLOCK_SKEW, is_late_entry
from app.modules.records.models import Encounter, Prescription
from app.modules.records.service import EncounterNotFoundError, EncounterNotOpenError
from app.modules.records.statuses import (
    EncounterStatus,
    MedicineRoute,
    PrescriptionStatus,
    VersionStatus,
)

# (box name for messages, longest allowed, required)
LIMITS: dict[str, tuple[str, int, bool]] = {
    "medicine": ("Medicine", 200, True),
    "strength": ("Strength", 50, False),
    "dose": ("Dose", 50, True),
    "frequency": ("How often", 80, True),
    "duration": ("How long", 50, True),
    "instructions": ("Instructions", 500, False),
}


class InvalidPrescriptionError(ValueError):
    """Something in the prescription is missing or not allowed."""


class PrescriptionNotFoundError(Exception):
    """No prescription with this ID in this clinic."""


class NotAPrescriberError(Exception):
    """Only an active doctor may write or change a prescription."""


@dataclass(frozen=True)
class PrescriptionDetails:
    medicine: str
    dose: str
    frequency: str
    duration: str
    route: str = MedicineRoute.ORAL.value
    strength: str | None = None
    instructions: str | None = None
    clinical_status: str = PrescriptionStatus.ACTIVE.value


def clean_prescription(details: PrescriptionDetails) -> dict:
    """Check a prescription and return the values to store."""
    values = asdict(details)
    clean: dict = {}
    for field, (label, longest, required) in LIMITS.items():
        text = " ".join((values[field] or "").split())
        if not text:
            if required:
                raise InvalidPrescriptionError(f"{label} cannot be empty.")
            clean[field] = None
            continue
        if len(text) > longest:
            raise InvalidPrescriptionError(f"{label} can be at most {longest} characters.")
        clean[field] = text
    try:
        clean["route"] = MedicineRoute(details.route).value
    except ValueError:
        allowed = ", ".join(route.value for route in MedicineRoute)
        raise InvalidPrescriptionError(f"Route must be one of: {allowed}.") from None
    try:
        clean["clinical_status"] = PrescriptionStatus(details.clinical_status).value
    except ValueError:
        allowed = ", ".join(status.value for status in PrescriptionStatus)
        raise InvalidPrescriptionError(f"Status must be one of: {allowed}.") from None
    return clean


def _require_prescriber(session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    if not is_active_prescriber(session, tenant_id=tenant_id, staff_id=actor_id):
        raise NotAPrescriberError("Only an active doctor can prescribe.")


def _encounter(session: Session, *, tenant_id: uuid.UUID, encounter_id: uuid.UUID) -> Encounter:
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    return found


def _existing(session: Session, *, tenant_id: uuid.UUID, prescription_id: uuid.UUID | None):
    if prescription_id is None:
        return None
    found = get_in_tenant(session, Prescription, tenant_id=tenant_id, row_id=prescription_id)
    return found if isinstance(found, Prescription) else None


def _clean_written_at(moment: datetime | None, now: datetime) -> datetime:
    if moment is None:
        return now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InvalidPrescriptionError("The time written must include a time zone.")
    if moment > now + CLOCK_SKEW:
        raise InvalidPrescriptionError("A prescription cannot be written in the future.")
    return moment.astimezone(UTC)


def write_prescription(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    details: PrescriptionDetails,
    prescription_id: uuid.UUID | None = None,
    written_at: datetime | None = None,
    now: datetime | None = None,
) -> Prescription:
    """Prescribe a medicine in an open encounter (or, written offline, before sign-off)."""
    current = now or datetime.now(UTC)
    _require_prescriber(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, prescription_id=prescription_id)
    if existing is not None:
        return existing

    values = clean_prescription(details)
    if values["clinical_status"] != PrescriptionStatus.ACTIVE.value:
        raise InvalidPrescriptionError("A new prescription starts as active.")
    written = _clean_written_at(written_at, current)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    late = is_late_entry(
        encounter,
        taken_at=written if written_at is not None else None,  # no device time: written now
        refusal="Prescriptions can only be written in an open encounter.",
    )
    prescription = Prescription(
        id=prescription_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        version_status=VersionStatus.CURRENT.value,
        recorded_by_id=actor_id,
        recorded_at=current,
        written_at=written,
        synced_late=late,
        **values,
    )
    session.add(prescription)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRESCRIPTION_WRITE,
        patient_id=encounter.patient_id,
        entity_id=prescription.id,
    )
    session.commit()
    session.refresh(prescription)
    return prescription


def revise_prescription(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    prescription_id: uuid.UUID,
    details: PrescriptionDetails,
    revision_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Prescription:
    """Stop or fix a prescription. Any active doctor may; the old version is kept.

    Changed elsewhere already (another device, offline): kept as a conflict.
    """
    current = now or datetime.now(UTC)
    _require_prescriber(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, prescription_id=revision_id)
    if existing is not None:
        return existing

    values = clean_prescription(details)
    statement = (
        tenant_select(Prescription, tenant_id)
        .where(col(Prescription.id) == prescription_id)
        .with_for_update()
    )
    old = session.exec(statement).first()
    if old is None:
        raise PrescriptionNotFoundError("Prescription not found.")
    new_status = new_version_status(old)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=old.encounter_id)
    if encounter.status == EncounterStatus.ENTERED_IN_ERROR.value:
        raise EncounterNotOpenError("This encounter was marked as entered in error.")

    if new_status == VersionStatus.CURRENT.value:
        old.version_status = VersionStatus.SUPERSEDED.value
    revised = Prescription(
        id=revision_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=old.encounter_id,
        patient_id=old.patient_id,
        version_status=new_status,
        replaces_id=old.id,
        recorded_by_id=actor_id,
        recorded_at=current,
        written_at=current,
        **values,
    )
    session.add(old)
    session.add(revised)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRESCRIPTION_REVISE,
        patient_id=old.patient_id,
        entity_id=revised.id,
    )
    session.commit()
    session.refresh(revised)
    return revised


def list_encounter_prescriptions(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    include_history: bool = False,
) -> list[Prescription]:
    """An encounter's prescriptions, oldest first: those in use and any conflicts.
    With history, earlier versions and ones entered in error are included too."""
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRESCRIPTION_VIEW,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    statement = tenant_select(Prescription, tenant_id).where(
        col(Prescription.encounter_id) == encounter_id
    )
    if not include_history:
        statement = statement.where(col(Prescription.version_status).in_(SHOWN)).where(
            col(Prescription.clinical_status) != PrescriptionStatus.ENTERED_IN_ERROR.value
        )
    statement = statement.order_by(col(Prescription.recorded_at))
    return list(session.exec(statement).all())


def resolve_prescription_conflict(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    conflict_id: uuid.UUID,
    keep_conflict: bool,
) -> Prescription:
    """Choose between two versions of a prescription. Any active doctor may."""
    _require_prescriber(session, tenant_id=tenant_id, actor_id=actor_id)
    kept = resolve_conflict(
        session,
        Prescription,
        tenant_id=tenant_id,
        conflict_id=conflict_id,
        keep_conflict=keep_conflict,
        not_found=PrescriptionNotFoundError,
        check_allowed=lambda conflict, current: None,
    )
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRESCRIPTION_RESOLVE,
        patient_id=kept.patient_id,
        entity_id=kept.id,
    )
    session.commit()
    session.refresh(kept)
    return kept
