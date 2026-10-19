"""The patient-facing summary of a visit, approved by the clinician (FR-R4).

Draft: any active doctor or nurse writes it in plain words; only its author edits it.
Approve: the clinician who opened the encounter, after sign-off (the record is then
complete). From that moment the wording never changes and the patient may read it.
Withdraw: the same clinician hides an approved summary that turned out wrong; it is
kept, and a new one can be drafted.

One summary at a time per encounter (a draft or an approved one); withdrawn ones
stay as history. The text is health information: never logged.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.records.models import Encounter, PatientSummary
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotEncounterOwnerError,
    _require_clinician,
)
from app.modules.records.statuses import EncounterStatus, SummaryStatus

MAX_SUMMARY_LENGTH = 4000


class InvalidSummaryError(ValueError):
    """The summary is empty or too long."""


class SummaryNotFoundError(Exception):
    """No summary with this ID in this clinic."""


class SummaryMoveError(Exception):
    """The summary cannot change like that (already approved, one already exists...)."""


class NotSummaryAuthorError(Exception):
    """Only whoever drafted a summary may edit the draft."""


def clean_summary(body: str) -> str:
    """Trim the ends but keep the line breaks: it is read as a letter."""
    text = (body or "").strip()
    if not text:
        raise InvalidSummaryError("A summary cannot be empty.")
    if len(text) > MAX_SUMMARY_LENGTH:
        raise InvalidSummaryError(f"A summary can be at most {MAX_SUMMARY_LENGTH} characters.")
    return text


def _encounter(session: Session, *, tenant_id: uuid.UUID, encounter_id: uuid.UUID) -> Encounter:
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    if found.status == EncounterStatus.ENTERED_IN_ERROR.value:
        raise EncounterNotOpenError("This encounter was marked as entered in error.")
    return found


def _locked(session: Session, *, tenant_id: uuid.UUID, summary_id: uuid.UUID) -> PatientSummary:
    statement = (
        tenant_select(PatientSummary, tenant_id)
        .where(col(PatientSummary.id) == summary_id)
        .with_for_update()
    )
    summary = session.exec(statement).first()
    if summary is None:
        raise SummaryNotFoundError("Summary not found.")
    return summary


def _audit(session, summary: PatientSummary, *, actor_id: uuid.UUID, action: AuditAction) -> None:
    add_audit_event(
        session,
        tenant_id=summary.tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=summary.patient_id,
        entity_id=summary.id,
    )


def draft_summary(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    body: str,
    summary_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> PatientSummary:
    """Start the summary of a visit. Refused while a draft or approved one exists."""
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    if summary_id is not None:
        existing = get_in_tenant(session, PatientSummary, tenant_id=tenant_id, row_id=summary_id)
        if isinstance(existing, PatientSummary):
            return existing
    text = clean_summary(body)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    live = session.exec(
        tenant_select(PatientSummary, tenant_id)
        .where(col(PatientSummary.encounter_id) == encounter.id)
        .where(col(PatientSummary.status) != SummaryStatus.WITHDRAWN.value)
        .with_for_update()
    ).first()
    if live is not None:
        raise SummaryMoveError("This visit already has a summary. Edit or withdraw that one.")

    summary = PatientSummary(
        id=summary_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        body=text,
        status=SummaryStatus.DRAFT.value,
        drafted_by_id=actor_id,
        drafted_at=current,
        updated_at=current,
    )
    session.add(summary)
    _audit(session, summary, actor_id=actor_id, action=AuditAction.SUMMARY_DRAFT)
    session.commit()
    session.refresh(summary)
    return summary


def edit_draft(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    summary_id: uuid.UUID,
    body: str,
    now: datetime | None = None,
) -> PatientSummary:
    """Change a draft's wording. Only its author, and only while it is a draft."""
    text = clean_summary(body)
    summary = _locked(session, tenant_id=tenant_id, summary_id=summary_id)
    if summary.status != SummaryStatus.DRAFT.value:
        raise SummaryMoveError("Only a draft can be edited. An approved summary never changes.")
    if summary.drafted_by_id != actor_id:
        raise NotSummaryAuthorError("Only the clinician who drafted this summary can edit it.")
    summary.body = text
    summary.updated_at = now or datetime.now(UTC)
    session.add(summary)
    _audit(session, summary, actor_id=actor_id, action=AuditAction.SUMMARY_EDIT)
    session.commit()
    session.refresh(summary)
    return summary


def approve_summary(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    summary_id: uuid.UUID,
    now: datetime | None = None,
) -> PatientSummary:
    """The encounter's clinician approves the draft after sign-off. The patient may read it."""
    summary = _locked(session, tenant_id=tenant_id, summary_id=summary_id)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=summary.encounter_id)
    if encounter.clinician_id != actor_id:
        raise NotEncounterOwnerError(
            "Only the clinician who opened this encounter can approve its summary."
        )
    if encounter.status != EncounterStatus.CLOSED.value:
        raise SummaryMoveError("Sign off the encounter first, so the summary matches the record.")
    if summary.status != SummaryStatus.DRAFT.value:
        raise SummaryMoveError("Only a draft can be approved.")
    summary.status = SummaryStatus.APPROVED.value
    summary.approved_by_id = actor_id
    summary.approved_at = now or datetime.now(UTC)
    session.add(summary)
    _audit(session, summary, actor_id=actor_id, action=AuditAction.SUMMARY_APPROVE)
    session.commit()
    session.refresh(summary)
    return summary


def withdraw_summary(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    summary_id: uuid.UUID,
    now: datetime | None = None,
) -> PatientSummary:
    """Hide an approved summary that turned out wrong. Kept; a new one can be drafted."""
    summary = _locked(session, tenant_id=tenant_id, summary_id=summary_id)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=summary.encounter_id)
    if encounter.clinician_id != actor_id:
        raise NotEncounterOwnerError(
            "Only the clinician who opened this encounter can withdraw its summary."
        )
    if summary.status != SummaryStatus.APPROVED.value:
        raise SummaryMoveError("Only an approved summary can be withdrawn.")
    summary.status = SummaryStatus.WITHDRAWN.value
    summary.withdrawn_by_id = actor_id
    summary.withdrawn_at = now or datetime.now(UTC)
    session.add(summary)
    _audit(session, summary, actor_id=actor_id, action=AuditAction.SUMMARY_WITHDRAW)
    session.commit()
    session.refresh(summary)
    return summary


def list_encounter_summaries(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, encounter_id: uuid.UUID
) -> list[PatientSummary]:
    """Every summary of a visit, newest first, withdrawn ones included. Reading is logged."""
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.SUMMARY_VIEW,
        patient_id=found.patient_id,
        entity_id=found.id,
    )
    session.commit()
    statement = (
        tenant_select(PatientSummary, tenant_id)
        .where(col(PatientSummary.encounter_id) == encounter_id)
        .order_by(col(PatientSummary.drafted_at).desc())
    )
    return list(session.exec(statement).all())


def approved_summaries_for_patient(
    session: Session, *, tenant_id: uuid.UUID, patient_id: uuid.UUID
) -> list[PatientSummary]:
    """What the patient may read (Step 8): approved summaries only, newest first.
    The caller records the look in the diary."""
    statement = (
        tenant_select(PatientSummary, tenant_id)
        .where(col(PatientSummary.patient_id) == patient_id)
        .where(col(PatientSummary.status) == SummaryStatus.APPROVED.value)
        .order_by(col(PatientSummary.approved_at).desc())
    )
    return list(session.exec(statement).all())
