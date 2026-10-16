"""What happens after a consultation: follow-up and referral (FR-C5).

Both are written in an encounter by a doctor or nurse, through the device outbox like
vitals and notes: the device makes the ID, and one written offline before sign-off is
accepted after it and marked synced_late (late.py).

A follow-up is then front desk's job: they see who is due (name, date, kind of visit;
never the clinical instructions), book the visit, and mark the follow-up booked or
cancelled. A referral's content is never edited; cancelling it keeps it.
"""
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.service import patient_names
from app.modules.records.late import CLOCK_SKEW, is_late_entry
from app.modules.records.models import Encounter, FollowUp, Referral
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    _require_clinician,
)
from app.modules.records.statuses import (
    EncounterStatus,
    FollowUpStatus,
    ReferralStatus,
    ReferralUrgency,
)
from app.modules.scheduling.service import get_appointment
from app.modules.scheduling.statuses import VisitType

MAX_INSTRUCTIONS = 500
MAX_TO_NAME = 200
MAX_SPECIALTY = 100
MAX_REASON = 2000
LONGEST_FOLLOW_UP = timedelta(days=366)


class InvalidOutcomeError(ValueError):
    """Something in the follow-up or referral is missing or not allowed."""


class FollowUpNotFoundError(Exception):
    """No follow-up with this ID in this clinic."""


class ReferralNotFoundError(Exception):
    """No referral with this ID in this clinic."""


class OutcomeMoveError(Exception):
    """The follow-up or referral cannot change like that (already booked, cancelled...)."""


class NotReferralAuthorError(Exception):
    """Only whoever wrote the referral, or the encounter's owner, may cancel it."""


def _text(value: str | None, *, field: str, longest: int, required: bool) -> str | None:
    clean = " ".join((value or "").split())
    if not clean:
        if required:
            raise InvalidOutcomeError(f"{field} cannot be empty.")
        return None
    if len(clean) > longest:
        raise InvalidOutcomeError(f"{field} can be at most {longest} characters.")
    return clean


def _clean_written_at(moment: datetime | None, now: datetime) -> datetime:
    if moment is None:
        return now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InvalidOutcomeError("The time written must include a time zone.")
    if moment > now + CLOCK_SKEW:
        raise InvalidOutcomeError("It cannot be written in the future.")
    return moment.astimezone(UTC)


def _encounter(session: Session, *, tenant_id: uuid.UUID, encounter_id: uuid.UUID) -> Encounter:
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    return found


def _audit(session, *, tenant_id, actor_id, action, patient_id=None, entity_id=None) -> None:
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        patient_id=patient_id,
        entity_id=entity_id,
    )


# Follow-up


def plan_follow_up(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    due_date: date,
    visit_type: str,
    instructions: str | None = None,
    follow_up_id: uuid.UUID | None = None,
    written_at: datetime | None = None,
    now: datetime | None = None,
) -> FollowUp:
    """Ask for the patient to be seen again by a date, in person or remotely."""
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    if follow_up_id is not None:
        existing = get_in_tenant(session, FollowUp, tenant_id=tenant_id, row_id=follow_up_id)
        if isinstance(existing, FollowUp):
            return existing

    try:
        kind = VisitType(visit_type).value
    except ValueError:
        raise InvalidOutcomeError("Kind must be in_person or teleconsult.") from None
    written = _clean_written_at(written_at, current)
    if not written.date() <= due_date <= written.date() + LONGEST_FOLLOW_UP:
        raise InvalidOutcomeError("The follow-up date must be from today to a year ahead.")
    note = _text(instructions, field="Instructions", longest=MAX_INSTRUCTIONS, required=False)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    late = is_late_entry(
        encounter,
        taken_at=written if written_at is not None else None,
        refusal="A follow-up can only be planned in an open encounter.",
    )

    follow_up = FollowUp(
        id=follow_up_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        due_date=due_date,
        visit_type=kind,
        instructions=note,
        status=FollowUpStatus.PLANNED.value,
        recorded_by_id=actor_id,
        recorded_at=current,
        written_at=written,
        synced_late=late,
    )
    session.add(follow_up)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.FOLLOW_UP_PLAN,
        patient_id=encounter.patient_id,
        entity_id=follow_up.id,
    )
    session.commit()
    session.refresh(follow_up)
    return follow_up


def list_encounter_follow_ups(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, encounter_id: uuid.UUID
) -> list[FollowUp]:
    """An encounter's follow-ups, with their instructions. Reading them is logged."""
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.FOLLOW_UP_VIEW,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    statement = (
        tenant_select(FollowUp, tenant_id)
        .where(col(FollowUp.encounter_id) == encounter_id)
        .order_by(col(FollowUp.recorded_at))
    )
    return list(session.exec(statement).all())


def follow_ups_due(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, until: date
) -> list[tuple[FollowUp, str]]:
    """Planned follow-ups due by `until` (overdue included), soonest first, with the
    patient's name. For front desk: the screen shows no instructions."""
    _audit(session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.FOLLOW_UP_LIST)
    session.commit()
    rows = session.exec(
        tenant_select(FollowUp, tenant_id)
        .where(col(FollowUp.status) == FollowUpStatus.PLANNED.value)
        .where(col(FollowUp.due_date) <= until)
        .order_by(col(FollowUp.due_date), col(FollowUp.recorded_at))
    ).all()
    names = patient_names(
        session, tenant_id=tenant_id, patient_ids=list({row.patient_id for row in rows})
    )
    return [(row, names.get(row.patient_id, "(name not found)")) for row in rows]


def _planned_follow_up(session: Session, *, tenant_id: uuid.UUID, follow_up_id: uuid.UUID):
    statement = (
        tenant_select(FollowUp, tenant_id).where(col(FollowUp.id) == follow_up_id).with_for_update()
    )
    follow_up = session.exec(statement).first()
    if follow_up is None:
        raise FollowUpNotFoundError("Follow-up not found.")
    if follow_up.status != FollowUpStatus.PLANNED.value:
        raise OutcomeMoveError("This follow-up was already booked or cancelled.")
    return follow_up


def mark_follow_up_booked(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    appointment_id: uuid.UUID | None = None,
) -> FollowUp:
    """Front desk booked the visit (optionally saying which one)."""
    follow_up = _planned_follow_up(session, tenant_id=tenant_id, follow_up_id=follow_up_id)
    if appointment_id is not None:
        visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
        if visit is None or visit.patient_id != follow_up.patient_id:
            raise InvalidOutcomeError("That visit is not this patient's.")
    follow_up.status = FollowUpStatus.BOOKED.value
    follow_up.appointment_id = appointment_id
    session.add(follow_up)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.FOLLOW_UP_BOOKED,
        patient_id=follow_up.patient_id,
        entity_id=follow_up.id,
    )
    session.commit()
    session.refresh(follow_up)
    return follow_up


def cancel_follow_up(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, follow_up_id: uuid.UUID
) -> FollowUp:
    """Not needed after all, or the patient declined. Kept, never deleted."""
    follow_up = _planned_follow_up(session, tenant_id=tenant_id, follow_up_id=follow_up_id)
    follow_up.status = FollowUpStatus.CANCELLED.value
    session.add(follow_up)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.FOLLOW_UP_CANCEL,
        patient_id=follow_up.patient_id,
        entity_id=follow_up.id,
    )
    session.commit()
    session.refresh(follow_up)
    return follow_up


# Referral


def write_referral(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    to_name: str,
    reason: str,
    urgency: str = ReferralUrgency.ROUTINE.value,
    specialty: str | None = None,
    referral_id: uuid.UUID | None = None,
    written_at: datetime | None = None,
    now: datetime | None = None,
) -> Referral:
    """Refer the patient to another clinic or specialist."""
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    if referral_id is not None:
        existing = get_in_tenant(session, Referral, tenant_id=tenant_id, row_id=referral_id)
        if isinstance(existing, Referral):
            return existing

    try:
        level = ReferralUrgency(urgency).value
    except ValueError:
        raise InvalidOutcomeError("Urgency must be routine, urgent or emergency.") from None
    values = {
        "to_name": _text(to_name, field="Referred to", longest=MAX_TO_NAME, required=True),
        "specialty": _text(specialty, field="Specialty", longest=MAX_SPECIALTY, required=False),
        # Line breaks matter in a letter: keep them, trim the ends.
        "reason": (reason or "").strip(),
    }
    if not values["reason"]:
        raise InvalidOutcomeError("Reason cannot be empty.")
    if len(values["reason"]) > MAX_REASON:
        raise InvalidOutcomeError(f"Reason can be at most {MAX_REASON} characters.")
    written = _clean_written_at(written_at, current)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    late = is_late_entry(
        encounter,
        taken_at=written if written_at is not None else None,
        refusal="A referral can only be written in an open encounter.",
    )

    referral = Referral(
        id=referral_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        urgency=level,
        status=ReferralStatus.ACTIVE.value,
        recorded_by_id=actor_id,
        recorded_at=current,
        written_at=written,
        synced_late=late,
        **values,
    )
    session.add(referral)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.REFERRAL_WRITE,
        patient_id=encounter.patient_id,
        entity_id=referral.id,
    )
    session.commit()
    session.refresh(referral)
    return referral


def list_encounter_referrals(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, encounter_id: uuid.UUID
) -> list[Referral]:
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.REFERRAL_VIEW,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    statement = (
        tenant_select(Referral, tenant_id)
        .where(col(Referral.encounter_id) == encounter_id)
        .order_by(col(Referral.recorded_at))
    )
    return list(session.exec(statement).all())


def get_referral(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, referral_id: uuid.UUID
) -> Referral:
    """One referral, for its letter. Reading it is logged."""
    referral = get_in_tenant(session, Referral, tenant_id=tenant_id, row_id=referral_id)
    if not isinstance(referral, Referral):
        raise ReferralNotFoundError("Referral not found.")
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.REFERRAL_VIEW,
        patient_id=referral.patient_id,
        entity_id=referral.id,
    )
    session.commit()
    session.refresh(referral)
    return referral


def cancel_referral(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, referral_id: uuid.UUID
) -> Referral:
    """Written by mistake, or no longer needed. Kept, never deleted."""
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    statement = (
        tenant_select(Referral, tenant_id).where(col(Referral.id) == referral_id).with_for_update()
    )
    referral = session.exec(statement).first()
    if referral is None:
        raise ReferralNotFoundError("Referral not found.")
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=referral.encounter_id)
    if encounter.status == EncounterStatus.ENTERED_IN_ERROR.value:
        raise EncounterNotOpenError("This encounter was marked as entered in error.")
    if actor_id not in (referral.recorded_by_id, encounter.clinician_id):
        raise NotReferralAuthorError(
            "Only whoever wrote this referral, or the encounter's owner, can cancel it."
        )
    if referral.status != ReferralStatus.ACTIVE.value:
        raise OutcomeMoveError("This referral was already cancelled.")
    referral.status = ReferralStatus.CANCELLED.value
    session.add(referral)
    _audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.REFERRAL_CANCEL,
        patient_id=referral.patient_id,
        entity_id=referral.id,
    )
    session.commit()
    session.refresh(referral)
    return referral
