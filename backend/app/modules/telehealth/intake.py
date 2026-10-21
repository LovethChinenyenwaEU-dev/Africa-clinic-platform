"""Teleconsult intake: reason, consent and the danger-sign screen before a remote visit.

FR-C2: before a consult, collect intake, consent and red-flag screening.
FR-C6: if a danger sign is present, advise in-person care and record the escalation.

Intake is the remote visit's check-in. With no danger signs the patient joins the
remote waiting room (the visit moves to "waiting" and shows on the queue). With a
danger sign the escalation is recorded, the advice is shown, and the remote visit
cannot check in or start (scheduling asks readiness.py). Staff then cancel it and
book the patient in person.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import PATIENT_PORTAL, AuditAction, add_audit_event
from app.modules.consent.service import has_active_consent
from app.modules.scheduling.lifecycle import AppointmentNotFoundError, check_in
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import get_appointment
from app.modules.scheduling.statuses import AppointmentStatus, RedFlag, VisitType
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.telehealth.models import TeleconsultIntake
from app.modules.telehealth.readiness import IntakeOutcome, latest_intake

MAX_REASON_LENGTH = 500
# Remote visits whose intake can still be taken (or taken again).
OPEN_STATUSES = frozenset({AppointmentStatus.BOOKED.value, AppointmentStatus.WAITING.value})

ESCALATION_ADVICE = (
    "A danger sign was reported. This needs in-person care, not a remote consultation. "
    "Ask the patient to come to the clinic now, or to go to the nearest emergency department."
)


class InvalidIntakeError(ValueError):
    """The intake is missing its reason, or names an unknown danger sign."""


class NotATeleconsultError(Exception):
    """Intake is only for remote visits."""


class TeleconsultConsentMissingError(Exception):
    """The patient has not consented to remote care (purpose: teleconsult)."""


def clean_intake(reason: str, red_flags: list[str]) -> tuple[str, list[str]]:
    text = " ".join(reason.split())
    if not text:
        raise InvalidIntakeError("Give the reason for the visit.")
    if len(text) > MAX_REASON_LENGTH:
        raise InvalidIntakeError(f"The reason can be at most {MAX_REASON_LENGTH} characters.")
    flags: list[str] = []
    for code in red_flags:
        try:
            flag = RedFlag(code).value
        except ValueError:
            raise InvalidIntakeError("Unknown danger sign.") from None
        if flag not in flags:
            flags.append(flag)
    return text, flags


def remote_visit(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    visit = get_appointment(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit is None:
        raise AppointmentNotFoundError("Appointment not found.")
    if visit.visit_type != VisitType.TELECONSULT.value:
        raise NotATeleconsultError("Intake is only for remote visits.")
    return visit


def submit_intake(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    reason: str,
    red_flags: list[str],
    intake_id: uuid.UUID | None = None,
    now: datetime | None = None,
    by_patient: bool = False,
) -> TeleconsultIntake:
    """Take the intake for a remote visit: staff on the phone or at the desk, or the
    patient on their own page (by_patient: actor_id is then the patient; the caller has
    checked that the visit is theirs)."""
    current = now or datetime.now(UTC)
    purpose = PATIENT_PORTAL if by_patient else None
    if intake_id is not None:
        existing = get_in_tenant(session, TeleconsultIntake, tenant_id=tenant_id, row_id=intake_id)
        if isinstance(existing, TeleconsultIntake):
            return existing  # the same request again: nothing new

    text, flags = clean_intake(reason, red_flags)
    visit = remote_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit.status not in OPEN_STATUSES:
        raise InvalidMoveError("Intake can only be taken before the remote visit starts.")
    if not has_active_consent(
        session, tenant_id=tenant_id, patient_id=visit.patient_id, purpose="teleconsult"
    ):
        raise TeleconsultConsentMissingError(
            "Record the patient's consent to remote care (teleconsult) first."
        )

    outcome = IntakeOutcome.ESCALATED if flags else IntakeOutcome.READY
    intake = TeleconsultIntake(
        id=intake_id or uuid.uuid4(),
        tenant_id=tenant_id,
        appointment_id=visit.id,
        patient_id=visit.patient_id,
        reason=text,
        red_flags=flags,
        outcome=outcome.value,
        source="patient" if by_patient else "staff",
        recorded_by_id=None if by_patient else actor_id,
        recorded_at=current,
    )
    session.add(intake)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TELECONSULT_INTAKE,
        patient_id=visit.patient_id,
        entity_id=intake.id,
        purpose=purpose,
    )
    if outcome is IntakeOutcome.ESCALATED:
        # FR-C6: the escalation itself is recorded, apart from the intake.
        add_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=AuditAction.TELECONSULT_ESCALATE,
            patient_id=visit.patient_id,
            entity_id=intake.id,
            purpose=purpose,
        )
    session.commit()
    session.refresh(intake)

    if outcome is IntakeOutcome.READY and visit.status == AppointmentStatus.BOOKED.value:
        # Into the remote waiting room: the visit now shows on the queue.
        check_in(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            appointment_id=visit.id,
            now=current,
            purpose=purpose,
        )
    return intake


def intake_history(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, appointment_id: uuid.UUID
) -> list[TeleconsultIntake]:
    """Every intake of one remote visit, newest first. Reading it is in the diary."""
    visit = remote_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TELECONSULT_INTAKE_VIEW,
        patient_id=visit.patient_id,
        entity_id=visit.id,
    )
    session.commit()
    statement = (
        tenant_select(TeleconsultIntake, tenant_id)
        .where(col(TeleconsultIntake.appointment_id) == appointment_id)
        .order_by(col(TeleconsultIntake.recorded_at).desc())
    )
    return list(session.exec(statement).all())


def teleconsult_status(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> tuple[bool, str | None]:
    """For the booking screens: has the patient consented to remote care, and what did
    the newest intake decide (ready, escalated, or None yet)? No clinical text."""
    visit = remote_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    consented = has_active_consent(
        session, tenant_id=tenant_id, patient_id=visit.patient_id, purpose="teleconsult"
    )
    latest = latest_intake(session, tenant_id=tenant_id, appointment_id=appointment_id)
    return consented, latest.outcome if latest else None
