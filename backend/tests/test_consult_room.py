"""Week 9 Step 5: the consult room. Video, audio or text, every switch recorded, and chat."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.service import grant_consent, publish_consent_text
from app.modules.identity.service import login
from app.modules.scheduling.lifecycle import complete_consultation, start_consultation
from app.modules.telehealth.intake import submit_intake
from app.modules.telehealth.room import (
    ConsultNotLiveError,
    InvalidConsultError,
    NotTheConsultingClinicianError,
    RoomNotOpenError,
    change_mode,
    list_messages,
    mode_history,
    open_room,
    room_links,
    send_message,
)
from app.modules.telehealth.video import JitsiProvider
from tests.scheduling_helpers import NOW, PASSWORD, book, build_clinic


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


@pytest.fixture(autouse=True)
def fake_video(monkeypatch):
    monkeypatch.setattr(settings, "video_provider", "fake")


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def remote_visit_in_progress(session, clinic, *, start=True):
    publish_consent_text(session, **who(clinic, "desk"), purpose="teleconsult", body="I agree.")
    grant_consent(
        session,
        **who(clinic, "desk"),
        patient_id=clinic["patient"].id,
        purpose="teleconsult",
        granted_by="patient",
    )
    visit = book(session, clinic, visit_type="teleconsult")
    submit_intake(
        session, **who(clinic, "desk"), appointment_id=visit.id, reason="Cough.", red_flags=[]
    )
    if start:
        start_consultation(session, **who(clinic), appointment_id=visit.id, now=NOW)
    return visit


def actions(session, clinic):
    return [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]


def test_jitsi_links_are_random_and_carry_no_names():
    provider = JitsiProvider("https://meet.example.org/")
    first, second = provider.new_room_name(), provider.new_room_name()

    links = provider.links(first)

    assert first != second and len(first) > 20
    assert links.video_url.startswith(f"https://meet.example.org/{first}#")
    assert "startAudioOnly=true" in links.audio_url


def test_the_consulting_clinician_opens_one_room_per_visit(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    room = open_room(session, **who(clinic), appointment_id=visit.id)
    again = open_room(session, **who(clinic), appointment_id=visit.id)

    assert room.id == again.id
    assert room.mode == "video"
    assert room_links(room).video_url.startswith("https://video.invalid/")
    assert actions(session, clinic).count("teleconsult.room_open") == 1


def test_only_the_consulting_clinician_opens_the_room(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    with pytest.raises(NotTheConsultingClinicianError):
        open_room(session, **who(clinic, "nurse"), appointment_id=visit.id)


def test_no_room_before_the_visit_starts_or_after_it_ends(session, clinics):
    clinic = clinics["a"]
    waiting = remote_visit_in_progress(session, clinic, start=False)

    with pytest.raises(ConsultNotLiveError):
        open_room(session, **who(clinic), appointment_id=waiting.id)

    start_consultation(session, **who(clinic), appointment_id=waiting.id, now=NOW)
    complete_consultation(session, **who(clinic), appointment_id=waiting.id, now=NOW)
    with pytest.raises(ConsultNotLiveError):
        open_room(session, **who(clinic), appointment_id=waiting.id)


def test_the_call_steps_down_video_audio_text_and_each_switch_is_recorded(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)
    open_room(session, **who(clinic), appointment_id=visit.id)

    change_mode(
        session, **who(clinic), appointment_id=visit.id, to_mode="audio", reason="poor_connection"
    )
    room = change_mode(
        session, **who(clinic), appointment_id=visit.id, to_mode="text", reason="poor_connection"
    )
    change_mode(  # already text: nothing to record
        session, **who(clinic), appointment_id=visit.id, to_mode="text", reason="poor_connection"
    )

    history = mode_history(session, tenant_id=clinic["tenant"].id, appointment_id=visit.id)
    assert room.mode == "text"
    assert [(row.from_mode, row.to_mode) for row in history] == [
        ("video", "audio"),
        ("audio", "text"),
    ]
    assert {row.reason for row in history} == {"poor_connection"}
    assert actions(session, clinic).count("teleconsult.mode") == 2


def test_switching_needs_an_open_room_and_known_codes(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    with pytest.raises(RoomNotOpenError):
        change_mode(
            session, **who(clinic), appointment_id=visit.id, to_mode="audio", reason="poor_connection"
        )
    open_room(session, **who(clinic), appointment_id=visit.id)
    with pytest.raises(InvalidConsultError):
        change_mode(
            session, **who(clinic), appointment_id=visit.id, to_mode="smoke", reason="poor_connection"
        )


def test_with_video_switched_off_the_room_is_text_only(session, clinics, monkeypatch):
    monkeypatch.setattr(settings, "video_provider", "none")
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    room = open_room(session, **who(clinic), appointment_id=visit.id)

    assert room.mode == "text"
    assert room_links(room).video_url is None
    with pytest.raises(InvalidConsultError):
        change_mode(
            session, **who(clinic), appointment_id=visit.id, to_mode="video", reason="patient_choice"
        )


def test_chat_messages_are_kept_in_order_and_a_re_send_appears_once(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)
    message_id = uuid.uuid4()

    first = send_message(
        session, **who(clinic), appointment_id=visit.id, body=" Hello. ", message_id=message_id,
        now=NOW,
    )
    send_message(
        session, **who(clinic), appointment_id=visit.id, body="Hello.", message_id=message_id
    )
    send_message(
        session, **who(clinic), appointment_id=visit.id, body="How is the cough?",
        now=NOW + timedelta(minutes=1),
    )

    everything = list_messages(session, **who(clinic), appointment_id=visit.id)
    newer = list_messages(
        session, **who(clinic), appointment_id=visit.id, since=NOW + timedelta(seconds=30)
    )

    assert first.body == "Hello."
    assert [m.body for m in everything] == ["Hello.", "How is the cough?"]
    assert [m.body for m in newer] == ["How is the cough?"]
    # Opening the chat is in the diary; the quiet check for new messages is not.
    assert actions(session, clinic).count("teleconsult.chat_view") == 1
    assert actions(session, clinic).count("teleconsult.message") == 2


@pytest.mark.parametrize("body", ["   ", "x" * 2001])
def test_empty_or_huge_messages_are_refused(session, clinics, body):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    with pytest.raises(InvalidConsultError):
        send_message(session, **who(clinic), appointment_id=visit.id, body=body)


def test_the_chat_stays_readable_after_the_visit_but_closes_for_writing(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)
    send_message(session, **who(clinic), appointment_id=visit.id, body="Take the tablets.")
    complete_consultation(session, **who(clinic), appointment_id=visit.id, now=NOW)

    with pytest.raises(ConsultNotLiveError):
        send_message(session, **who(clinic), appointment_id=visit.id, body="One more thing.")
    assert len(list_messages(session, **who(clinic, "nurse"), appointment_id=visit.id)) == 1


def test_the_room_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]
    visit = remote_visit_in_progress(session, clinic)

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    base = f"/api/v1/teleconsults/{visit.id}"
    doctor = bearer("doctor")
    by_desk = client.post(f"{base}/room", headers=bearer("front_desk"))
    opened = client.post(f"{base}/room", headers=doctor)
    switched = client.post(
        f"{base}/mode", json={"mode": "audio", "reason": "poor_connection"}, headers=doctor
    )
    sent = client.post(f"{base}/messages", json={"body": "Can you hear me?"}, headers=doctor)
    desk_reads = client.get(f"{base}/messages", headers=bearer("front_desk"))
    nurse_reads = client.get(f"{base}/messages", headers=bearer("nurse"))

    assert by_desk.status_code == 403
    assert opened.status_code == 200
    assert opened.json()["mode"] == "video"
    assert opened.json()["video_url"].startswith("https://video.invalid/")
    assert switched.json()["mode"] == "audio"
    assert sent.status_code == 201
    assert desk_reads.status_code == 403
    assert [m["body"] for m in nurse_reads.json()] == ["Can you hear me?"]
