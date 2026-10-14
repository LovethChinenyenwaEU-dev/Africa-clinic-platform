"""Allergies and problems: the patient's lists that every visit sees.

Every entry is made inside an open encounter for that patient, so each line
says which visit it came from and who wrote it. A change (inactive, resolved,
a typo fixed) is a new version; the old one is kept, unchanged.

The words a clinician types here are health information: they are never put in
logs or error messages.
"""
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.service import PatientNotFoundError, patient_exists
from app.modules.records.models import Allergy, Encounter, Problem
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotCurrentVersionError,
    _require_clinician,
)
from app.modules.records.statuses import (
    AllergySeverity,
    AllergyStatus,
    EncounterStatus,
    ProblemCategory,
    ProblemStatus,
    VersionStatus,
)

MAX_SUBSTANCE_LENGTH = 200
MAX_REACTION_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 500
# ICD-10 shape: a letter, two characters, then an optional dot and up to four more. B54, J45.9
ICD10_CODE = re.compile(r"^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")

ChartModel = type[Allergy] | type[Problem]


class InvalidChartEntryError(ValueError):
    """Something in the allergy or problem is missing or not allowed."""


class AllergyNotFoundError(Exception):
    """No allergy with this ID in this clinic."""


class ProblemNotFoundError(Exception):
    """No problem with this ID in this clinic."""


class WrongPatientError(Exception):
    """The encounter belongs to a different patient."""


@dataclass(frozen=True)
class AllergyDetails:
    substance: str
    reaction: str | None = None
    severity: str = AllergySeverity.UNKNOWN.value
    clinical_status: str = AllergyStatus.ACTIVE.value


@dataclass(frozen=True)
class ProblemDetails:
    description: str
    category: str = ProblemCategory.PROBLEM_LIST.value
    code: str | None = None
    clinical_status: str = ProblemStatus.ACTIVE.value
    onset_date: date | None = None


def _text(value: str | None, *, field: str, max_length: int, required: bool) -> str | None:
    clean = " ".join((value or "").split())
    if not clean:
        if required:
            raise InvalidChartEntryError(f"{field} cannot be empty.")
        return None
    if len(clean) > max_length:
        raise InvalidChartEntryError(f"{field} can be at most {max_length} characters.")
    return clean


def _choice(value: str, choices: type[StrEnum], field: str) -> str:
    try:
        return choices(value).value
    except ValueError:
        allowed = ", ".join(choice.value for choice in choices)
        raise InvalidChartEntryError(f"{field} must be one of: {allowed}.") from None


def clean_allergy(details: AllergyDetails) -> dict:
    """Check an allergy and return the values to store."""
    return {
        "substance": _text(
            details.substance, field="Substance", max_length=MAX_SUBSTANCE_LENGTH, required=True
        ),
        "reaction": _text(
            details.reaction, field="Reaction", max_length=MAX_REACTION_LENGTH, required=False
        ),
        "severity": _choice(details.severity, AllergySeverity, "Severity"),
        "clinical_status": _choice(details.clinical_status, AllergyStatus, "Status"),
    }


def clean_problem(details: ProblemDetails, *, today: date) -> dict:
    """Check a problem or diagnosis and return the values to store."""
    code = (details.code or "").strip().upper() or None
    if code is not None and not ICD10_CODE.match(code):
        raise InvalidChartEntryError("Code must look like an ICD-10 code, for example B54.")
    if details.onset_date is not None and details.onset_date > today:
        raise InvalidChartEntryError("Onset date cannot be in the future.")
    return {
        "description": _text(
            details.description,
            field="Description",
            max_length=MAX_DESCRIPTION_LENGTH,
            required=True,
        ),
        "category": _choice(details.category, ProblemCategory, "Category"),
        "code": code,
        "clinical_status": _choice(details.clinical_status, ProblemStatus, "Status"),
        "onset_date": details.onset_date,
    }


def _working_encounter(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    encounter_id: uuid.UUID,
    patient_id: uuid.UUID | None = None,
) -> Encounter:
    """The open encounter an entry is made in. It must be for the same patient."""
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    if patient_id is not None and found.patient_id != patient_id:
        raise WrongPatientError("That encounter is for a different patient.")
    if found.status != EncounterStatus.OPEN.value:
        raise EncounterNotOpenError("Entries can only be made in an open encounter.")
    return found


def _existing(session: Session, model: ChartModel, *, tenant_id: uuid.UUID, entry_id):
    """An entry this request already created (same device ID), so a replay changes nothing."""
    if entry_id is None:
        return None
    found = get_in_tenant(session, model, tenant_id=tenant_id, row_id=entry_id)
    return found if isinstance(found, model) else None


def _add(
    session: Session,
    model: ChartModel,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    values: dict,
    entry_id: uuid.UUID | None,
    action: AuditAction,
    now: datetime | None,
):
    current = now or datetime.now(UTC)
    existing = _existing(session, model, tenant_id=tenant_id, entry_id=entry_id)
    if existing is not None:
        return existing

    encounter = _working_encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    entry = model(
        id=entry_id or uuid.uuid4(),
        tenant_id=tenant_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        version_status=VersionStatus.CURRENT.value,
        recorded_by_id=actor_id,
        recorded_at=current,
        **values,
    )
    session.add(entry)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=encounter.patient_id,
    )
    session.commit()
    session.refresh(entry)
    return entry


def _revise(
    session: Session,
    model: ChartModel,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    entry_id: uuid.UUID,
    encounter_id: uuid.UUID,
    values: dict,
    revision_id: uuid.UUID | None,
    not_found: type[Exception],
    action: AuditAction,
    now: datetime | None,
):
    current = now or datetime.now(UTC)
    existing = _existing(session, model, tenant_id=tenant_id, entry_id=revision_id)
    if existing is not None:
        return existing

    statement = tenant_select(model, tenant_id).where(col(model.id) == entry_id).with_for_update()
    old = session.exec(statement).first()
    if old is None:
        raise not_found("Not found.")
    if old.version_status != VersionStatus.CURRENT.value:
        raise NotCurrentVersionError("This was already changed; change the newest version.")
    encounter = _working_encounter(
        session, tenant_id=tenant_id, encounter_id=encounter_id, patient_id=old.patient_id
    )

    old.version_status = VersionStatus.SUPERSEDED.value
    revised = model(
        id=revision_id or uuid.uuid4(),
        tenant_id=tenant_id,
        patient_id=old.patient_id,
        encounter_id=encounter.id,
        version_status=VersionStatus.CURRENT.value,
        replaces_id=old.id,
        recorded_by_id=actor_id,
        recorded_at=current,
        **values,
    )
    session.add(old)
    session.add(revised)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=old.patient_id,
    )
    session.commit()
    session.refresh(revised)
    return revised


def _list(
    session: Session,
    model: ChartModel,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    include_history: bool,
    action: AuditAction,
) -> list:
    if not patient_exists(session, tenant_id=tenant_id, patient_id=patient_id):
        raise PatientNotFoundError("Patient not found.")
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=action, patient_id=patient_id
    )
    session.commit()
    statement = tenant_select(model, tenant_id).where(col(model.patient_id) == patient_id)
    if not include_history:
        statement = statement.where(
            col(model.version_status) == VersionStatus.CURRENT.value
        ).where(col(model.clinical_status) != "entered_in_error")
    statement = statement.order_by(col(model.recorded_at))
    return list(session.exec(statement).all())


def record_allergy(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    details: AllergyDetails,
    allergy_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Allergy:
    """Add an allergy to the patient's list, from inside an open encounter."""
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    return _add(
        session,
        Allergy,
        tenant_id=tenant_id,
        actor_id=actor_id,
        encounter_id=encounter_id,
        values=clean_allergy(details),
        entry_id=allergy_id,
        action=AuditAction.ALLERGY_RECORD,
        now=now,
    )


def revise_allergy(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    allergy_id: uuid.UUID,
    encounter_id: uuid.UUID,
    details: AllergyDetails,
    revision_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Allergy:
    """Change an allergy (for example mark it inactive). The old version is kept."""
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    return _revise(
        session,
        Allergy,
        tenant_id=tenant_id,
        actor_id=actor_id,
        entry_id=allergy_id,
        encounter_id=encounter_id,
        values=clean_allergy(details),
        revision_id=revision_id,
        not_found=AllergyNotFoundError,
        action=AuditAction.ALLERGY_REVISE,
        now=now,
    )


def list_patient_allergies(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    include_history: bool = False,
) -> list[Allergy]:
    """The patient's allergies, oldest first. Reading them is logged."""
    return _list(
        session,
        Allergy,
        tenant_id=tenant_id,
        actor_id=actor_id,
        patient_id=patient_id,
        include_history=include_history,
        action=AuditAction.ALLERGY_VIEW,
    )


def record_problem(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    details: ProblemDetails,
    problem_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Problem:
    """Add a problem or diagnosis to the patient's list, from inside an open encounter."""
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    today = (now or datetime.now(UTC)).date()
    return _add(
        session,
        Problem,
        tenant_id=tenant_id,
        actor_id=actor_id,
        encounter_id=encounter_id,
        values=clean_problem(details, today=today),
        entry_id=problem_id,
        action=AuditAction.PROBLEM_RECORD,
        now=now,
    )


def revise_problem(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    problem_id: uuid.UUID,
    encounter_id: uuid.UUID,
    details: ProblemDetails,
    revision_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Problem:
    """Change a problem (for example mark it resolved). The old version is kept."""
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    today = (now or datetime.now(UTC)).date()
    return _revise(
        session,
        Problem,
        tenant_id=tenant_id,
        actor_id=actor_id,
        entry_id=problem_id,
        encounter_id=encounter_id,
        values=clean_problem(details, today=today),
        revision_id=revision_id,
        not_found=ProblemNotFoundError,
        action=AuditAction.PROBLEM_REVISE,
        now=now,
    )


def list_patient_problems(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    include_history: bool = False,
) -> list[Problem]:
    """The patient's problems and diagnoses, oldest first. Reading them is logged."""
    return _list(
        session,
        Problem,
        tenant_id=tenant_id,
        actor_id=actor_id,
        patient_id=patient_id,
        include_history=include_history,
        action=AuditAction.PROBLEM_VIEW,
    )
