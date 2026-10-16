import uuid
from datetime import datetime
from enum import StrEnum

from sqlmodel import Session, col

from app.core.device import current_device_id
from app.core.tenant_scope import tenant_select
from app.modules.audit.models import AuditEvent

# The actor for things the platform does by itself, like sending a reminder.
# No staff row has this ID, so a diary reader can always tell it apart from a person.
SYSTEM_ACTOR_ID = uuid.UUID(int=0)


class AuditAction(StrEnum):
    """Every kind of thing we write in the diary. Add a new one only when a feature needs it."""

    PATIENT_CREATE = "patient.create"
    PATIENT_VIEW = "patient.view"
    PATIENT_SEARCH = "patient.search"
    PATIENT_REVIEW_LIST = "patient.review_list"  # opened the list of registrations to review
    PATIENT_REVIEW = "patient.review"  # decided: someone new, or already registered
    CONSENT_GRANT = "consent.grant"
    CONSENT_REVOKE = "consent.revoke"
    CONSENT_VIEW = "consent.view"
    AUDIT_VIEW = "audit.view"
    APPOINTMENT_CREATE = "appointment.create"
    APPOINTMENT_CHECK_IN = "appointment.check_in"
    APPOINTMENT_START = "appointment.start"
    APPOINTMENT_COMPLETE = "appointment.complete"
    APPOINTMENT_CANCEL = "appointment.cancel"
    APPOINTMENT_NO_SHOW = "appointment.no_show"
    APPOINTMENT_RESCHEDULE = "appointment.reschedule"
    QUEUE_VIEW = "queue.view"
    APPOINTMENT_LIST = "appointment.list"
    REMINDER_SEND = "reminder.send"
    ENCOUNTER_CREATE = "encounter.create"
    ENCOUNTER_CLOSE = "encounter.close"
    ENCOUNTER_ENTERED_IN_ERROR = "encounter.entered_in_error"
    ENCOUNTER_VIEW = "encounter.view"
    ENCOUNTER_LIST = "encounter.list"
    VITALS_RECORD = "vitals.record"
    VITALS_CORRECT = "vitals.correct"
    VITALS_VIEW = "vitals.view"
    ALLERGY_RECORD = "allergy.record"
    ALLERGY_REVISE = "allergy.revise"
    ALLERGY_VIEW = "allergy.view"
    PROBLEM_RECORD = "problem.record"
    PROBLEM_REVISE = "problem.revise"
    PROBLEM_VIEW = "problem.view"
    NOTE_WRITE = "note.write"
    NOTE_AMEND = "note.amend"
    NOTE_VIEW = "note.view"
    VITALS_RESOLVE = "vitals.resolve"
    ALLERGY_RESOLVE = "allergy.resolve"
    PROBLEM_RESOLVE = "problem.resolve"
    NOTE_RESOLVE = "note.resolve"
    PRESCRIPTION_WRITE = "prescription.write"
    PRESCRIPTION_REVISE = "prescription.revise"  # stopped or corrected: a new version
    PRESCRIPTION_VIEW = "prescription.view"
    PRESCRIPTION_RESOLVE = "prescription.resolve"

def add_audit_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: AuditAction,
    patient_id: uuid.UUID | None = None,
    purpose: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> AuditEvent:
    """Add a diary line to the open transaction.

    It does NOT save. The caller saves once, together with the action itself, so
    the action and its diary line either both happen or neither does.
    entity_id says exactly which record was touched (a note, a vitals set...).
    The device is taken from the request being handled, when there is one.
    """
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action.value,
        patient_id=patient_id,
        entity_id=entity_id,
        device_id=current_device_id(),
        purpose=purpose,
    )
    session.add(event)
    return event


class InvalidAuditFilterError(ValueError):
    """The date range for reading the diary does not make sense."""


def _check_range(since: datetime | None, until: datetime | None) -> None:
    for name, moment in (("since", since), ("until", until)):
        if moment is not None and (moment.tzinfo is None or moment.utcoffset() is None):
            raise InvalidAuditFilterError(f"{name} must include a time zone.")
    if since is not None and until is not None and since >= until:
        raise InvalidAuditFilterError("since must be earlier than until.")


def list_audit_events(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    patient_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """Newest first, only this clinic's lines. since is inclusive, until is exclusive."""
    _check_range(since, until)

    statement = tenant_select(AuditEvent, tenant_id)
    if patient_id is not None:
        statement = statement.where(col(AuditEvent.patient_id) == patient_id)
    if staff_id is not None:
        statement = statement.where(col(AuditEvent.actor_id) == staff_id)
    if since is not None:
        statement = statement.where(col(AuditEvent.occurred_at) >= since)
    if until is not None:
        statement = statement.where(col(AuditEvent.occurred_at) < until)
    statement = statement.order_by(col(AuditEvent.occurred_at).desc()).limit(limit)
    return list(session.exec(statement).all())

MAX_AUDIT_PAGE = 200


def view_audit_log(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    """Read the diary. Reading the diary is itself written in the diary.

    A bad date range is refused before anything is written or read.
    """
    _check_range(since, until)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.AUDIT_VIEW,
        patient_id=patient_id,
    )
    session.commit()
    return list_audit_events(
        session,
        tenant_id=tenant_id,
        patient_id=patient_id,
        staff_id=staff_id,
        since=since,
        until=until,
        limit=min(limit, MAX_AUDIT_PAGE),
    )