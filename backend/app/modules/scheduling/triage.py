"""Triage: how urgent a waiting patient is (P-03, FR-C6).

A nurse or doctor sets the level and ticks any danger signs. A danger sign always
makes the visit an emergency: the screen cannot lower it, and neither can the API.
The queue shows emergencies first, then urgent visits, then the rest in arrival order.

Codes only, never free text: the clinical detail belongs in the encounter.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import is_active_clinician
from app.modules.scheduling.lifecycle import AppointmentNotFoundError
from app.modules.scheduling.models import Appointment, Triage
from app.modules.scheduling.service import InvalidAppointmentError, get_appointment
from app.modules.scheduling.statuses import (
    TRIAGE_RANK,
    UNTRIAGED_RANK,
    AppointmentStatus,
    RedFlag,
    TriageLevel,
)
from app.modules.scheduling.transitions import InvalidMoveError

# Triage is for patients who are here: checked in, or already with a clinician.
TRIAGE_STATUSES = frozenset({AppointmentStatus.WAITING.value, AppointmentStatus.IN_CONSULT.value})


class NotAClinicianToTriageError(Exception):
    """Only an active doctor or nurse may triage."""


def clean_triage(level: str, red_flags: list[str]) -> tuple[str, list[str]]:
    """Check the codes. Any danger sign makes it an emergency, whatever was chosen."""
    try:
        chosen = TriageLevel(level)
    except ValueError:
        allowed = ", ".join(choice.value for choice in TriageLevel)
        raise InvalidAppointmentError(f"Level must be one of: {allowed}.") from None
    flags: list[str] = []
    for code in red_flags:
        try:
            flag = RedFlag(code).value
        except ValueError:
            raise InvalidAppointmentError("Unknown danger sign.") from None
        if flag not in flags:
            flags.append(flag)
    if flags:
        chosen = TriageLevel.EMERGENCY
    return chosen.value, flags


def record_triage(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    level: str,
    red_flags: list[str],
    triage_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Triage:
    """Triage (or triage again) a patient who is here. The newest triage counts."""
    if not is_active_clinician(session, tenant_id=tenant_id, staff_id=actor_id):
        raise NotAClinicianToTriageError("Only an active doctor or nurse can triage.")
    if triage_id is not None:
        existing = get_in_tenant(session, Triage, tenant_id=tenant_id, row_id=triage_id)
        if isinstance(existing, Triage):
            return existing  # the same request again: nothing new

    clean_level, flags = clean_triage(level, red_flags)
    visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit is None:
        raise AppointmentNotFoundError("Appointment not found.")
    if visit.status not in TRIAGE_STATUSES:
        raise InvalidMoveError("Only a patient who has checked in can be triaged.")

    triage = Triage(
        id=triage_id or uuid.uuid4(),
        tenant_id=tenant_id,
        appointment_id=visit.id,
        patient_id=visit.patient_id,
        level=clean_level,
        red_flags=flags,
        recorded_by_id=actor_id,
        recorded_at=now or datetime.now(UTC),
    )
    session.add(triage)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TRIAGE_RECORD,
        patient_id=visit.patient_id,
        entity_id=triage.id,
    )
    session.commit()
    session.refresh(triage)
    return triage


def triage_history(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, appointment_id: uuid.UUID
) -> list[Triage]:
    """Every triage of one visit, newest first. Reading it is in the diary."""
    visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit is None:
        raise AppointmentNotFoundError("Appointment not found.")
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TRIAGE_VIEW,
        patient_id=visit.patient_id,
        entity_id=visit.id,
    )
    session.commit()
    statement = (
        tenant_select(Triage, tenant_id)
        .where(col(Triage.appointment_id) == appointment_id)
        .order_by(col(Triage.recorded_at).desc())
    )
    return list(session.exec(statement).all())


def latest_triage(
    session: Session, *, tenant_id: uuid.UUID, visits: list[Appointment]
) -> dict[uuid.UUID, Triage]:
    """The triage that counts for each visit, in one query. No diary line: the caller
    shows it on a screen it already records (the queue)."""
    if not visits:
        return {}
    statement = tenant_select(Triage, tenant_id).where(
        col(Triage.appointment_id).in_([visit.id for visit in visits])
    )
    newest: dict[uuid.UUID, Triage] = {}
    for row in session.exec(statement).all():
        known = newest.get(row.appointment_id)
        if known is None or (row.recorded_at, str(row.id)) > (known.recorded_at, str(known.id)):
            newest[row.appointment_id] = row
    return newest


def urgency_rank(triage: Triage | None) -> int:
    """Where a visit sorts in the waiting line: emergencies first. Not triaged counts as
    standard, so an untriaged patient keeps their place in arrival order."""
    return TRIAGE_RANK[TriageLevel(triage.level)] if triage else UNTRIAGED_RANK
