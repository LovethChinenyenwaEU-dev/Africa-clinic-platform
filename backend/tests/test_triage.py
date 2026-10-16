"""Week 9 Step 2: triage. Urgent patients go first; danger signs always mean emergency."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.scheduling.board import get_queue
from app.modules.scheduling.lifecycle import (
    AppointmentNotFoundError,
    complete_consultation,
    start_consultation,
)
from app.modules.scheduling.service import InvalidAppointmentError
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.scheduling.triage import (
    NotAClinicianToTriageError,
    clean_triage,
    record_triage,
    triage_history,
)
from tests.scheduling_helpers import NOW, PASSWORD, book, build_clinic, walk_in


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="nurse"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def triage(session, clinic, visit, level="standard", red_flags=(), person="nurse", **extra):
    return record_triage(
        session,
        **who(clinic, person),
        appointment_id=visit.id,
        level=level,
        red_flags=list(red_flags),
        **extra,
    )


def queue(session, clinic):
    return get_queue(
        session, **who(clinic, "desk"), branch_id=clinic["branch"].id, now=NOW
    )


def test_a_danger_sign_always_makes_it_an_emergency():
    assert clean_triage("standard", ["chest_pain"]) == ("emergency", ["chest_pain"])
    assert clean_triage("urgent", []) == ("urgent", [])
    # The same sign twice is kept once.
    assert clean_triage("emergency", ["convulsions", "convulsions"]) == (
        "emergency",
        ["convulsions"],
    )


@pytest.mark.parametrize("level,flags", [("very bad", []), ("urgent", ["feels unwell"])])
def test_unknown_codes_are_refused(level, flags):
    with pytest.raises(InvalidAppointmentError):
        clean_triage(level, flags)


def test_emergencies_then_urgent_then_arrival_order(session, clinics):
    clinic = clinics["a"]
    first = walk_in(session, clinic, now=NOW)
    second = walk_in(session, clinic, now=NOW + timedelta(minutes=1))
    third = walk_in(session, clinic, now=NOW + timedelta(minutes=2))
    fourth = walk_in(session, clinic, now=NOW + timedelta(minutes=3))
    triage(session, clinic, third, level="urgent")
    triage(session, clinic, fourth, red_flags=["difficulty_breathing"])
    triage(session, clinic, first, level="standard")

    entries = queue(session, clinic)

    assert [entry.appointment_id for entry in entries] == [fourth.id, third.id, first.id, second.id]
    assert [entry.position for entry in entries] == [1, 2, 3, 4]
    assert [entry.triage_level for entry in entries] == ["emergency", "urgent", "standard", None]
    assert entries[0].red_flags == ("difficulty_breathing",)


def test_triaging_again_counts_the_newest_and_keeps_the_history(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic, now=NOW)
    triage(session, clinic, visit, level="standard", now=NOW)
    triage(session, clinic, visit, level="urgent", person="doctor", now=NOW + timedelta(minutes=5))

    [entry] = queue(session, clinic)
    history = triage_history(session, **who(clinic, "doctor"), appointment_id=visit.id)

    assert entry.triage_level == "urgent"
    assert [row.level for row in history] == ["urgent", "standard"]  # newest first
    actions = [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]
    assert actions.count("triage.record") == 2
    assert actions.count("triage.view") == 1


def test_a_re_sent_triage_is_recorded_once(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic, now=NOW)
    device_id = uuid.uuid4()

    first = triage(session, clinic, visit, level="urgent", triage_id=device_id)
    again = triage(session, clinic, visit, level="urgent", triage_id=device_id)

    assert first.id == again.id == device_id
    assert len(triage_history(session, **who(clinic), appointment_id=visit.id)) == 1


def test_only_clinicians_triage(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic, now=NOW)

    with pytest.raises(NotAClinicianToTriageError):
        triage(session, clinic, visit, person="desk")


def test_only_patients_who_are_here_are_triaged(session, clinics):
    clinic = clinics["a"]
    not_arrived = book(session, clinic)
    finished = walk_in(session, clinic, now=NOW)
    start_consultation(session, **who(clinic, "doctor"), appointment_id=finished.id, now=NOW)
    complete_consultation(session, **who(clinic, "doctor"), appointment_id=finished.id, now=NOW)

    for visit in (not_arrived, finished):
        with pytest.raises(InvalidMoveError):
            triage(session, clinic, visit)


def test_another_clinic_cannot_triage_or_read(session, clinics):
    visit = walk_in(session, clinics["a"], now=NOW)

    with pytest.raises(AppointmentNotFoundError):
        triage(session, clinics["b"], visit)
    with pytest.raises(AppointmentNotFoundError):
        triage_history(session, **who(clinics["b"]), appointment_id=visit.id)


def test_through_the_api_front_desk_sees_urgency_but_not_danger_signs(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]
    visit = walk_in(session, clinic, now=NOW)

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    url = f"/api/v1/appointments/{visit.id}/triage"
    by_desk = client.post(url, json={"level": "urgent"}, headers=bearer("front_desk"))
    by_nurse = client.post(
        url, json={"level": "standard", "red_flags": ["chest_pain"]}, headers=bearer("nurse")
    )
    params = {"branch_id": str(clinic["branch"].id)}
    queue_url = "/api/v1/appointments/queue"
    desk_view = client.get(queue_url, params=params, headers=bearer("front_desk"))
    nurse_view = client.get(queue_url, params=params, headers=bearer("nurse"))
    desk_history = client.get(url, headers=bearer("front_desk"))

    assert by_desk.status_code == 403
    assert by_nurse.status_code == 201
    assert by_nurse.json()["level"] == "emergency"
    assert desk_view.json()[0]["triage_level"] == "emergency"
    assert desk_view.json()[0]["red_flags"] == []
    assert "chest_pain" not in desk_view.text
    assert nurse_view.json()[0]["red_flags"] == ["chest_pain"]
    assert desk_history.status_code == 403


def test_the_danger_signs_match_the_screen():
    """The frontend's RED_FLAG_LABELS has words for exactly these 12 codes."""
    from app.modules.scheduling.statuses import RedFlag

    assert len(RedFlag) == 12
