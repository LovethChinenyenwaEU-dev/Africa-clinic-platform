"""What a signed-in patient does themselves (Week 9 Step 8b): agree to remote care, book
a free remote slot, answer the intake (the same danger-sign screen staff use), join the
consult room and chat.

Every function first checks that the visit is the patient's own; another patient's
visit answers exactly like one that does not exist. The patient is the actor in the
diary, with purpose "patient_portal".
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import PATIENT_PORTAL, AuditAction, add_audit_event
from app.modules.consent.service import (
    current_consent_text,
    grant_consent,
    has_active_consent,
)
from app.modules.identity.service import is_active_clinician, list_active_clinicians
from app.modules.patients.models import Patient
from app.modules.scheduling.availability import free_slots, is_free_slot
from app.modules.scheduling.lifecycle import AppointmentNotFoundError
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import book_appointment, get_appointment
from app.modules.scheduling.statuses import ACTIVE_STATUSES, VisitType
from app.modules.telehealth.intake import submit_intake
from app.modules.telehealth.models import ConsultMessage, TeleconsultIntake
from app.modules.telehealth.room import (
    RoomNotOpenError,
    find_room,
    list_messages,
    room_links,
    send_message,
)
from app.modules.telehealth.video import RoomLinks

REMOTE = VisitType.TELECONSULT.value
DAYS_SHOWN = 7


class SlotNotFreeError(Exception):
    """That time is not a free remote slot (taken meanwhile, or never offered)."""


class AlreadyBookedError(Exception):
    """The patient already has a remote visit booked from their own page."""


@dataclass(frozen=True)
class RemoteSlot:
    clinician_id: uuid.UUID
    clinician_name: str
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class RemoteCareConsent:
    consented: bool
    wording: str | None  # the clinic's current wording; None if it has published none
    version: int | None


def own_visit(session: Session, *, patient: Patient, appointment_id: uuid.UUID) -> Appointment:
    """The patient's own visit, or "not found" (also for another patient's visit)."""
    visit = get_appointment(session, tenant_id=patient.tenant_id, appointment_id=appointment_id)
    if visit is None or visit.patient_id != patient.id:
        raise AppointmentNotFoundError("Appointment not found.")
    return visit


# Consent to remote care


def remote_care_consent(session: Session, *, patient: Patient) -> RemoteCareConsent:
    text = current_consent_text(session, tenant_id=patient.tenant_id, purpose=REMOTE)
    consented = has_active_consent(
        session, tenant_id=patient.tenant_id, patient_id=patient.id, purpose=REMOTE
    )
    return RemoteCareConsent(
        consented=consented,
        wording=text.body if text else None,
        version=text.version if text else None,
    )


def agree_to_remote_care(session: Session, *, patient: Patient) -> None:
    """The patient read the clinic's wording and agreed, on their own page."""
    grant_consent(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        patient_id=patient.id,
        purpose=REMOTE,
        granted_by="patient",
        via=PATIENT_PORTAL,
    )


# Booking a free remote slot


def remote_slots(
    session: Session, *, patient: Patient, from_day: date, now: datetime | None = None
) -> list[RemoteSlot]:
    """Free remote slots of every active clinician for a week, earliest first."""
    found: list[RemoteSlot] = []
    for clinician in list_active_clinicians(session, tenant_id=patient.tenant_id):
        for slot in free_slots(
            session,
            tenant_id=patient.tenant_id,
            clinician_id=clinician.id,
            visit_type=REMOTE,
            from_day=from_day,
            days=DAYS_SHOWN,
            now=now,
        ):
            found.append(
                RemoteSlot(
                    clinician_id=clinician.id,
                    clinician_name=clinician.full_name,
                    starts_at=slot.starts_at,
                    ends_at=slot.ends_at,
                )
            )
    return sorted(found, key=lambda slot: (slot.starts_at, slot.clinician_name))


def book_remote_visit(
    session: Session,
    *,
    patient: Patient,
    clinician_id: uuid.UUID,
    starts_at: datetime,
    appointment_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> Appointment:
    """Book a free remote slot. One remote visit booked from the patient page at a time."""
    current = now or datetime.now(UTC)
    if appointment_id is not None:
        existing = get_appointment(
            session, tenant_id=patient.tenant_id, appointment_id=appointment_id
        )
        if existing is not None and existing.patient_id == patient.id:
            return existing  # the same booking sent twice

    waiting = session.exec(
        tenant_select(Appointment, patient.tenant_id)
        .where(col(Appointment.patient_id) == patient.id)
        .where(col(Appointment.booked_via) == PATIENT_PORTAL)
        .where(col(Appointment.visit_type) == REMOTE)
        .where(col(Appointment.status).in_([status.value for status in ACTIVE_STATUSES]))
        .where(col(Appointment.ends_at) > current)
    ).first()
    if waiting is not None:
        raise AlreadyBookedError(
            "You already have a remote visit booked. Cancel it with the clinic to choose another."
        )

    if not is_active_clinician(session, tenant_id=patient.tenant_id, staff_id=clinician_id):
        raise SlotNotFreeError("That time is no longer free. Please choose another.")
    slot = is_free_slot(
        session,
        tenant_id=patient.tenant_id,
        clinician_id=clinician_id,
        visit_type=REMOTE,
        starts_at=starts_at,
        now=current,
    )
    if slot is None:
        raise SlotNotFreeError("That time is no longer free. Please choose another.")
    minutes = int((slot.ends_at - slot.starts_at).total_seconds() // 60)
    return book_appointment(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        patient_id=patient.id,
        branch_id=slot.branch_id,
        clinician_id=clinician_id,
        starts_at=slot.starts_at,
        duration_minutes=minutes,
        visit_type=REMOTE,
        now=current,
        via=PATIENT_PORTAL,
        appointment_id=appointment_id,
    )


# Intake, room and chat


def answer_intake(
    session: Session,
    *,
    patient: Patient,
    appointment_id: uuid.UUID,
    reason: str,
    red_flags: list[str],
    intake_id: uuid.UUID | None = None,
) -> TeleconsultIntake:
    own_visit(session, patient=patient, appointment_id=appointment_id)
    return submit_intake(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        appointment_id=appointment_id,
        reason=reason,
        red_flags=red_flags,
        intake_id=intake_id,
        by_patient=True,
    )


def join_room(
    session: Session, *, patient: Patient, appointment_id: uuid.UUID
) -> tuple[str, RoomLinks]:
    """The call's mode and links, once the clinician has started the visit and opened
    the room."""
    visit = own_visit(session, patient=patient, appointment_id=appointment_id)
    room = find_room(session, tenant_id=patient.tenant_id, appointment_id=visit.id)
    if room is None or visit.status != "in_consult":
        raise RoomNotOpenError("The clinician has not opened the room yet. Please wait here.")
    add_audit_event(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        action=AuditAction.PORTAL_ROOM_VIEW,
        patient_id=patient.id,
        entity_id=room.id,
        purpose=PATIENT_PORTAL,
    )
    session.commit()
    return room.mode, room_links(room)


def write_in_chat(
    session: Session,
    *,
    patient: Patient,
    appointment_id: uuid.UUID,
    body: str,
    message_id: uuid.UUID | None = None,
) -> ConsultMessage:
    own_visit(session, patient=patient, appointment_id=appointment_id)
    return send_message(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        appointment_id=appointment_id,
        body=body,
        message_id=message_id,
        by_patient=True,
    )


def read_chat(
    session: Session, *, patient: Patient, appointment_id: uuid.UUID, since: datetime | None
) -> list[ConsultMessage]:
    own_visit(session, patient=patient, appointment_id=appointment_id)
    return list_messages(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,
        appointment_id=appointment_id,
        since=since,
        by_patient=True,
    )
