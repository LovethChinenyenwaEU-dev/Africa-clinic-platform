import uuid
from enum import StrEnum

from sqlmodel import Session, col

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
    REMINDER_SEND = "reminder.send"
    ENCOUNTER_CREATE = "encounter.create"
    ENCOUNTER_CLOSE = "encounter.close"
    ENCOUNTER_ENTERED_IN_ERROR = "encounter.entered_in_error"
    ENCOUNTER_VIEW = "encounter.view"
    ENCOUNTER_LIST = "encounter.list"
    VITALS_RECORD = "vitals.record"
    VITALS_CORRECT = "vitals.correct"
    VITALS_VIEW = "vitals.view"

def add_audit_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: AuditAction,
    patient_id: uuid.UUID | None = None,
    purpose: str | None = None,
) -> AuditEvent:
    """Add a diary line to the open transaction.

    It does NOT save. The caller saves once, together with the action itself, so
    the action and its diary line either both happen or neither does.
    """
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action.value,
        patient_id=patient_id,
        purpose=purpose,
    )
    session.add(event)
    return event


def list_audit_events(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    patient_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """Newest first, only this clinic's lines."""
    statement = tenant_select(AuditEvent, tenant_id)
    if patient_id is not None:
        statement = statement.where(col(AuditEvent.patient_id) == patient_id)
    statement = statement.order_by(col(AuditEvent.occurred_at).desc()).limit(limit)
    return list(session.exec(statement).all())

MAX_AUDIT_PAGE = 200


def view_audit_log(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    """Read the diary. Reading the diary is itself written in the diary."""
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
        limit=min(limit, MAX_AUDIT_PAGE),
    )