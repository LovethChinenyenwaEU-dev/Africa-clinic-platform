import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import BranchNotFoundError
from app.modules.scheduling.statuses import AppointmentStatus as Status
from app.modules.tenancy.service import get_branch


@dataclass(frozen=True)
class QueueEntry:
    """One line on the board. IDs, codes and times only: no names."""

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    clinician_id: uuid.UUID | None
    kind: str
    visit_type: str
    status: str
    position: int | None  # place in the waiting line; None while in consultation
    scheduled_at: datetime
    checked_in_at: datetime | None
    consult_started_at: datetime | None


def _entry(row: Appointment, position: int | None) -> QueueEntry:
    return QueueEntry(
        appointment_id=row.id,
        patient_id=row.patient_id,
        clinician_id=row.clinician_id,
        kind=row.kind,
        visit_type=row.visit_type,
        status=row.status,
        position=position,
        scheduled_at=row.starts_at,
        checked_in_at=row.checked_in_at,
        consult_started_at=row.consult_started_at,
    )


def get_queue(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> list[QueueEntry]:
    """Who is being seen and who is waiting at this branch. Looking is noted in the diary."""
    if get_branch(session, tenant_id=tenant_id, branch_id=branch_id) is None:
        raise BranchNotFoundError("Branch not found.")

    # One diary line per look. It records THAT the board was viewed, never whom it showed.
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.QUEUE_VIEW,
        purpose="queue",
    )
    session.commit()

    live = [Status.WAITING.value, Status.IN_CONSULT.value]
    statement = (
        tenant_select(Appointment, tenant_id)
        .where(col(Appointment.branch_id) == branch_id)
        .where(col(Appointment.status).in_(live))
    )
    rows = session.exec(statement).all()

    in_consult = sorted(
        (row for row in rows if row.status == Status.IN_CONSULT.value),
        key=lambda row: (row.consult_started_at or row.starts_at, str(row.id)),
    )
    waiting = sorted(
        (row for row in rows if row.status == Status.WAITING.value),
        key=lambda row: (row.checked_in_at or row.starts_at, str(row.id)),
    )

    entries = [_entry(row, None) for row in in_consult]
    entries += [_entry(row, place) for place, row in enumerate(waiting, start=1)]
    return entries