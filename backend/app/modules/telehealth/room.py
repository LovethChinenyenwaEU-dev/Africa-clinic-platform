"""The consult room: video, audio or text, and the chat (FR-C3, FR-C4).

The clinician running a remote visit opens its room once it has started. The video
itself runs at the provider (video.py); this keeps the room, which mode the call is
in, and every switch with its reason. When the connection is poor the call steps
down: video, then audio, then text. Text is the chat here, which works on any
connection because each check for new messages is a small request.

Chat messages are health information: never logged, never edited, never deleted.
Opening the chat is in the diary; the quiet checks for new messages every few
seconds are not, or the diary would fill with them.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import AppointmentStatus
from app.modules.telehealth.intake import remote_visit
from app.modules.telehealth.models import ConsultMessage, ConsultModeChange, ConsultRoom
from app.modules.telehealth.video import RoomLinks, get_video_provider, provider_named

MAX_MESSAGE_LENGTH = 2000


class ConsultMode(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"


class ModeChangeReason(StrEnum):
    POOR_CONNECTION = "poor_connection"
    PATIENT_CHOICE = "patient_choice"
    CLINICIAN_CHOICE = "clinician_choice"


class ConsultNotLiveError(Exception):
    """The remote visit has not started, or is over."""


class NotTheConsultingClinicianError(Exception):
    """Only the clinician running this remote visit may do this."""


class InvalidConsultError(ValueError):
    """An empty or too long message, or a mode this provider cannot offer."""


class RoomNotOpenError(Exception):
    """The room has not been opened yet."""


def _live(session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
    visit = remote_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if visit.status != AppointmentStatus.IN_CONSULT.value:
        raise ConsultNotLiveError("The remote visit is not in progress.")
    return visit


def _require_consulting(visit: Appointment, actor_id: uuid.UUID) -> None:
    if visit.clinician_id != actor_id:
        raise NotTheConsultingClinicianError("Only the clinician running this visit can do this.")


def find_room(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> ConsultRoom | None:
    statement = tenant_select(ConsultRoom, tenant_id).where(
        col(ConsultRoom.appointment_id) == appointment_id
    )
    return session.exec(statement).first()


def room_links(room: ConsultRoom) -> RoomLinks:
    """The links for this room, from the provider it was opened with."""
    return provider_named(room.provider).links(room.room_name)


def open_room(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, appointment_id: uuid.UUID
) -> ConsultRoom:
    """Open (or reopen) the room of a remote visit in progress. Opening twice is one room."""
    visit = _live(session, tenant_id=tenant_id, appointment_id=appointment_id)
    _require_consulting(visit, actor_id)
    existing = find_room(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if existing is not None:
        return existing

    provider = get_video_provider()
    room_name = provider.new_room_name()
    has_video = provider.links(room_name).video_url is not None
    room = ConsultRoom(
        tenant_id=tenant_id,
        appointment_id=visit.id,
        provider=provider.name,
        room_name=room_name,
        mode=ConsultMode.VIDEO.value if has_video else ConsultMode.TEXT.value,
        opened_by_id=actor_id,
    )
    session.add(room)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TELECONSULT_ROOM_OPEN,
        patient_id=visit.patient_id,
        entity_id=room.id,
    )
    session.commit()
    session.refresh(room)
    return room


def change_mode(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    to_mode: str,
    reason: str,
    now: datetime | None = None,
) -> ConsultRoom:
    """Switch the call between video, audio and text, and record why (FR-C4)."""
    try:
        mode = ConsultMode(to_mode)
        why = ModeChangeReason(reason)
    except ValueError:
        raise InvalidConsultError("Unknown mode or reason.") from None
    visit = _live(session, tenant_id=tenant_id, appointment_id=appointment_id)
    _require_consulting(visit, actor_id)
    room = find_room(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if room is None:
        raise RoomNotOpenError("Open the consult room first.")
    if mode is not ConsultMode.TEXT and room_links(room).video_url is None:
        raise InvalidConsultError("Video and audio are switched off here: use the chat.")
    if room.mode == mode.value:
        return room  # nothing to change, nothing to record

    session.add(
        ConsultModeChange(
            tenant_id=tenant_id,
            appointment_id=visit.id,
            from_mode=room.mode,
            to_mode=mode.value,
            reason=why.value,
            changed_by_id=actor_id,
            changed_at=now or datetime.now(UTC),
        )
    )
    room.mode = mode.value
    session.add(room)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TELECONSULT_MODE,
        patient_id=visit.patient_id,
        entity_id=room.id,
    )
    session.commit()
    session.refresh(room)
    return room


def mode_history(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> list[ConsultModeChange]:
    """Every switch, oldest first. Codes only, so no diary line."""
    statement = (
        tenant_select(ConsultModeChange, tenant_id)
        .where(col(ConsultModeChange.appointment_id) == appointment_id)
        .order_by(col(ConsultModeChange.changed_at))
    )
    return list(session.exec(statement).all())


def send_message(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    body: str,
    message_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ConsultMessage:
    """The clinician writes in the chat. Sending the same message ID again adds nothing."""
    if message_id is not None:
        existing = get_in_tenant(session, ConsultMessage, tenant_id=tenant_id, row_id=message_id)
        if isinstance(existing, ConsultMessage):
            return existing
    text = body.strip()
    if not text:
        raise InvalidConsultError("A message cannot be empty.")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise InvalidConsultError(f"A message can be at most {MAX_MESSAGE_LENGTH} characters.")
    visit = _live(session, tenant_id=tenant_id, appointment_id=appointment_id)
    _require_consulting(visit, actor_id)

    message = ConsultMessage(
        id=message_id or uuid.uuid4(),
        tenant_id=tenant_id,
        appointment_id=visit.id,
        sender="staff",
        sender_staff_id=actor_id,
        body=text,
        sent_at=now or datetime.now(UTC),
    )
    session.add(message)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.TELECONSULT_MESSAGE,
        patient_id=visit.patient_id,
        entity_id=message.id,
    )
    session.commit()
    session.refresh(message)
    return message


def list_messages(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    appointment_id: uuid.UUID,
    since: datetime | None = None,
) -> list[ConsultMessage]:
    """The chat, oldest first. Without `since` this is opening the chat (in the diary);
    with it, a quiet check for messages sent at or after that moment (the screen
    drops the ones it already has)."""
    visit = remote_visit(session, tenant_id=tenant_id, appointment_id=appointment_id)
    if since is None:
        add_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=AuditAction.TELECONSULT_CHAT_VIEW,
            patient_id=visit.patient_id,
            entity_id=visit.id,
        )
        session.commit()
    statement = tenant_select(ConsultMessage, tenant_id).where(
        col(ConsultMessage.appointment_id) == appointment_id
    )
    if since is not None:
        statement = statement.where(col(ConsultMessage.sent_at) >= since)
    statement = statement.order_by(col(ConsultMessage.sent_at), col(ConsultMessage.id))
    return list(session.exec(statement).all())
