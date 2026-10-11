import uuid
from enum import StrEnum

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.models import AuditEvent


class AuditAction(StrEnum):
    """Every kind of thing we write in the diary. Add a new one only when a feature needs it."""

    PATIENT_CREATE = "patient.create"
    PATIENT_VIEW = "patient.view"
    PATIENT_SEARCH = "patient.search"


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