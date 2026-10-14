"""Clinical notes: write, amend and read.

A note is a clinician's own words, so only its author may amend it. Anyone who
disagrees writes a note of their own. An amendment is a new version; the old
wording is kept, unchanged, and can always be read in the history.

Note text is never put in logs or error messages.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.records.chart import _working_encounter
from app.modules.records.models import ClinicalNote, Encounter
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotCurrentVersionError,
    _require_clinician,
)
from app.modules.records.statuses import EncounterStatus, NoteKind, VersionStatus

MAX_NOTE_LENGTH = 10_000


class InvalidNoteError(ValueError):
    """The note is empty, too long, or of an unknown kind."""


class NoteNotFoundError(Exception):
    """No note with this ID in this clinic."""


class NotNoteAuthorError(Exception):
    """Only the clinician who wrote a note may amend it."""


def clean_body(body: str) -> str:
    """Trim the ends but keep the clinician's line breaks."""
    clean = body.strip()
    if not clean:
        raise InvalidNoteError("A note cannot be empty.")
    if len(clean) > MAX_NOTE_LENGTH:
        raise InvalidNoteError(f"A note can be at most {MAX_NOTE_LENGTH} characters.")
    return clean


def clean_kind(kind: str) -> str:
    try:
        return NoteKind(kind).value
    except ValueError:
        allowed = ", ".join(choice.value for choice in NoteKind)
        raise InvalidNoteError(f"Kind must be one of: {allowed}.") from None


def _existing(session: Session, *, tenant_id: uuid.UUID, note_id: uuid.UUID | None):
    if note_id is None:
        return None
    found = get_in_tenant(session, ClinicalNote, tenant_id=tenant_id, row_id=note_id)
    return found if isinstance(found, ClinicalNote) else None


def write_note(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    kind: str,
    body: str,
    note_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ClinicalNote:
    """Add a note to an open encounter. Any active clinician may write their own note."""
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, note_id=note_id)
    if existing is not None:
        return existing

    values = {"kind": clean_kind(kind), "body": clean_body(body)}
    encounter = _working_encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    note = ClinicalNote(
        id=note_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        version_status=VersionStatus.CURRENT.value,
        recorded_by_id=actor_id,
        recorded_at=current,
        **values,
    )
    session.add(note)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.NOTE_WRITE,
        patient_id=encounter.patient_id,
        entity_id=note.id,
    )
    session.commit()
    session.refresh(note)
    return note


def amend_note(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    note_id: uuid.UUID,
    body: str,
    amendment_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ClinicalNote:
    """Replace the wording of your own note. Allowed after sign-off; the old wording stays."""
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, note_id=amendment_id)
    if existing is not None:
        return existing

    new_body = clean_body(body)
    statement = (
        tenant_select(ClinicalNote, tenant_id)
        .where(col(ClinicalNote.id) == note_id)
        .with_for_update()
    )
    old = session.exec(statement).first()
    if old is None:
        raise NoteNotFoundError("Note not found.")
    if old.version_status != VersionStatus.CURRENT.value:
        raise NotCurrentVersionError("This note was already amended; amend the newest version.")
    if old.recorded_by_id != actor_id:
        raise NotNoteAuthorError("Only the clinician who wrote this note can amend it.")
    encounter = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=old.encounter_id)
    if not isinstance(encounter, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    if encounter.status == EncounterStatus.ENTERED_IN_ERROR.value:
        raise EncounterNotOpenError("This encounter was marked as entered in error.")

    old.version_status = VersionStatus.SUPERSEDED.value
    amended = ClinicalNote(
        id=amendment_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=old.encounter_id,
        patient_id=old.patient_id,
        version_status=VersionStatus.CURRENT.value,
        replaces_id=old.id,
        kind=old.kind,
        body=new_body,
        recorded_by_id=actor_id,
        recorded_at=current,
    )
    session.add(old)
    session.add(amended)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.NOTE_AMEND,
        patient_id=old.patient_id,
        entity_id=amended.id,
    )
    session.commit()
    session.refresh(amended)
    return amended


def list_encounter_notes(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    include_history: bool = False,
) -> list[ClinicalNote]:
    """An encounter's notes, oldest first. With history, earlier wordings are included."""
    encounter = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(encounter, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.NOTE_VIEW,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    statement = tenant_select(ClinicalNote, tenant_id).where(
        col(ClinicalNote.encounter_id) == encounter_id
    )
    if not include_history:
        statement = statement.where(col(ClinicalNote.version_status) == VersionStatus.CURRENT.value)
    statement = statement.order_by(col(ClinicalNote.recorded_at))
    return list(session.exec(statement).all())
