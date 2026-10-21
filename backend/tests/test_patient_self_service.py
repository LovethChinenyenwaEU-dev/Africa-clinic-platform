"""Week 9 Step 8b: the patient agrees to remote care, books a free remote slot, answers
the intake, joins the consult room and chats, all on their own page."""
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.service import NoConsentTextError, publish_consent_text
from app.modules.identity.tokens import create_patient_token
from app.modules.patients.service import create_patient
from app.modules.portal.selfservice import (
    AlreadyBookedError,
    SlotNotFreeError,
    agree_to_remote_care,
    answer_intake,
    book_remote_visit,
    join_room,
    read_chat,
    remote_care_consent,
    remote_slots,
    write_in_chat,
)
from app.modules.scheduling.availability import add_availability
from app.modules.scheduling.lifecycle import (
    AppointmentNotFoundError,
    complete_consultation,
    start_consultation,
)
from app.modules.scheduling.service import get_appointment
from app.modules.telehealth.intake import TeleconsultConsentMissingError
from app.modules.telehealth.room import (
    ConsultNotLiveError,
    RoomNotOpenError,
    list_messages,
    open_room,
)
from tests.scheduling_helpers import build_clinic

# Next week's Monday, counted from today, so these tests never age.
TODAY = datetime.now(UTC).date()
MONDAY = TODAY + timedelta(days=7 - TODAY.weekday())


def lagos(hour: int, minute: int = 0, day: date = MONDAY) -> datetime:
    """A Lagos clock time as a UTC moment (Lagos is UTC+1 all year)."""
    return datetime(day.year, day.month, day.day, hour - 1, minute, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fake_video(monkeypatch):
    monkeypatch.setattr(settings, "video_provider", "fake")


@pytest.fixture
def clinic(session, run_id):
    """A clinic whose doctor offers remote visits on Mondays 09:00-10:00, 30-minute slots."""
    data = build_clinic(session, run_id, "a")
    add_availability(
        session,
        tenant_id=data["tenant"].id,
        actor_id=data["doctor"].id,
        branch_id=data["branch"].id,
        weekday=0,
        starts=time(9, 0),
        ends=time(10, 0),
        visit_type="teleconsult",
        slot_minutes=30,
    )
    return data


def staff(clinic, person):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def publish_wording(session, clinic):
    publish_consent_text(
        session, **staff(clinic, "desk"), purpose="teleconsult", body="I agree to remote care."
    )


def book(session, clinic, minute=0, patient=None, **extra):
    return book_remote_visit(
        session,
        patient=patient or clinic["patient"],
        clinician_id=clinic["doctor"].id,
        starts_at=lagos(9, minute),
        **extra,
    )


def portal_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [e.action for e in events if e.purpose == "patient_portal"]


# Consent


def test_the_patient_reads_the_wording_and_agrees(session, clinic):
    publish_wording(session, clinic)
    patient = clinic["patient"]

    before = remote_care_consent(session, patient=patient)
    agree_to_remote_care(session, patient=patient)
    after = remote_care_consent(session, patient=patient)

    assert before.consented is False and before.wording == "I agree to remote care."
    assert after.consented is True
    assert "consent.grant" in portal_lines(session, clinic)


def test_no_agreement_before_the_clinic_publishes_its_wording(session, clinic):
    with pytest.raises(NoConsentTextError):
        agree_to_remote_care(session, patient=clinic["patient"])


# Booking


def test_free_slots_are_offered_with_the_clinicians_name(session, clinic):
    slots = remote_slots(session, patient=clinic["patient"], from_day=MONDAY)

    assert [slot.starts_at for slot in slots] == [lagos(9, 0), lagos(9, 30)]
    assert {slot.clinician_name for slot in slots} == {"Test doctor"}


def test_the_patient_books_a_free_slot_themselves(session, clinic):
    visit = book(session, clinic, minute=30)

    assert visit.visit_type == "teleconsult"
    assert visit.status == "booked"
    assert visit.booked_via == "patient_portal"
    assert visit.created_by_id is None  # no staff member booked it
    assert visit.ends_at - visit.starts_at == timedelta(minutes=30)
    assert "appointment.create" in portal_lines(session, clinic)
    assert [s.starts_at for s in remote_slots(session, patient=clinic["patient"], from_day=MONDAY)] == [
        lagos(9, 0)
    ]


def test_a_booking_sent_twice_is_made_once_and_one_at_a_time(session, clinic):
    device_id = uuid.uuid4()

    first = book(session, clinic, appointment_id=device_id)
    again = book(session, clinic, appointment_id=device_id)

    assert first.id == again.id == device_id
    with pytest.raises(AlreadyBookedError):
        book(session, clinic, minute=30)


def test_only_a_free_slot_can_be_booked(session, clinic):
    other = create_patient(
        session,
        **staff(clinic, "desk"),
        full_name="Other Patient",
        date_of_birth=date(1985, 1, 1),
        sex="male",
        confirmed_not_duplicate=True,
    )
    book(session, clinic, patient=other)

    with pytest.raises(SlotNotFreeError):  # taken by someone else
        book(session, clinic)
    with pytest.raises(SlotNotFreeError):  # not on the slot grid
        book(session, clinic, minute=10)


# Intake, room, chat


def test_the_patients_own_intake_puts_them_in_the_remote_waiting_room(session, clinic):
    publish_wording(session, clinic)
    patient = clinic["patient"]
    visit = book(session, clinic)

    with pytest.raises(TeleconsultConsentMissingError):
        answer_intake(session, patient=patient, appointment_id=visit.id, reason="Cough.", red_flags=[])
    agree_to_remote_care(session, patient=patient)
    intake = answer_intake(
        session, patient=patient, appointment_id=visit.id, reason="Cough.", red_flags=[]
    )

    assert intake.outcome == "ready"
    assert intake.source == "patient" and intake.recorded_by_id is None
    status = get_appointment(session, tenant_id=patient.tenant_id, appointment_id=visit.id).status
    assert status == "waiting"
    assert {"teleconsult.intake", "appointment.check_in"} <= set(portal_lines(session, clinic))


def test_a_danger_sign_on_the_patients_own_intake_sends_them_in_person(session, clinic):
    publish_wording(session, clinic)
    patient = clinic["patient"]
    agree_to_remote_care(session, patient=patient)
    visit = book(session, clinic)

    intake = answer_intake(
        session,
        patient=patient,
        appointment_id=visit.id,
        reason="Chest pain.",
        red_flags=["chest_pain"],
    )

    assert intake.outcome == "escalated"
    assert "teleconsult.escalate" in portal_lines(session, clinic)


def test_the_patient_joins_the_room_and_chats_once_the_clinician_has_opened_it(session, clinic):
    publish_wording(session, clinic)
    patient = clinic["patient"]
    agree_to_remote_care(session, patient=patient)
    visit = book(session, clinic)
    answer_intake(session, patient=patient, appointment_id=visit.id, reason="Cough.", red_flags=[])

    with pytest.raises(RoomNotOpenError):
        join_room(session, patient=patient, appointment_id=visit.id)
    start_consultation(session, **staff(clinic, "doctor"), appointment_id=visit.id)
    open_room(session, **staff(clinic, "doctor"), appointment_id=visit.id)

    mode, links = join_room(session, patient=patient, appointment_id=visit.id)
    write_in_chat(session, patient=patient, appointment_id=visit.id, body="Hello doctor.")

    assert mode == "video" and links.video_url.startswith("https://video.invalid/")
    seen_by_doctor = list_messages(session, **staff(clinic, "doctor"), appointment_id=visit.id)
    assert [(m.sender, m.body) for m in seen_by_doctor] == [("patient", "Hello doctor.")]
    assert seen_by_doctor[0].sender_staff_id is None
    assert len(read_chat(session, patient=patient, appointment_id=visit.id, since=None)) == 1
    assert {"portal.room_view", "teleconsult.message"} <= set(portal_lines(session, clinic))

    complete_consultation(session, **staff(clinic, "doctor"), appointment_id=visit.id)
    with pytest.raises(ConsultNotLiveError):
        write_in_chat(session, patient=patient, appointment_id=visit.id, body="One more thing.")


def test_nobody_reaches_another_patients_visit(session, clinic):
    publish_wording(session, clinic)
    visit = book(session, clinic)
    stranger = create_patient(
        session,
        **staff(clinic, "desk"),
        full_name="Stranger",
        date_of_birth=date(1970, 1, 1),
        sex="female",
        confirmed_not_duplicate=True,
    )

    for attempt in (
        lambda: answer_intake(
            session, patient=stranger, appointment_id=visit.id, reason="x", red_flags=[]
        ),
        lambda: join_room(session, patient=stranger, appointment_id=visit.id),
        lambda: write_in_chat(session, patient=stranger, appointment_id=visit.id, body="x"),
        lambda: read_chat(session, patient=stranger, appointment_id=visit.id, since=None),
    ):
        with pytest.raises(AppointmentNotFoundError):
            attempt()


def test_remote_care_through_the_api(session, clinic):
    client = TestClient(app)
    publish_wording(session, clinic)
    patient = clinic["patient"]
    token = create_patient_token(patient_id=patient.id, tenant_id=patient.tenant_id)
    headers = {"Authorization": f"Bearer {token}"}
    base = "/api/v1/patient-portal"

    slots = client.get(f"{base}/remote-slots", params={"from_day": MONDAY.isoformat()}, headers=headers)
    agreed = client.post(f"{base}/remote-care/consent", headers=headers)
    booking = {"clinician_id": str(clinic["doctor"].id), "starts_at": lagos(9).isoformat()}
    booked = client.post(f"{base}/visits", json=booking, headers=headers)
    twice = client.post(
        f"{base}/visits", json={**booking, "starts_at": lagos(9, 30).isoformat()}, headers=headers
    )
    visit_id = booked.json()["appointment_id"]
    intake = client.post(
        f"{base}/visits/{visit_id}/intake",
        json={"reason": "Chest pain", "red_flags": ["chest_pain"]},
        headers=headers,
    )
    room = client.get(f"{base}/visits/{visit_id}/room", headers=headers)

    assert slots.status_code == 200 and len(slots.json()) == 2
    assert agreed.json()["consented"] is True
    assert booked.status_code == 201
    assert booked.json()["clinician_name"] == "Test doctor"
    assert twice.status_code == 409
    assert intake.json()["outcome"] == "escalated"
    assert "in-person care" in intake.json()["advice"]
    assert room.status_code == 409
