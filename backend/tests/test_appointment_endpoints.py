import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.scheduling.lifecycle import start_consultation
from app.modules.tenancy.service import create_branch
from tests.scheduling_helpers import (
    NOW,
    PASSWORD,
    appointment_actions,
    book,
    build_clinic,
    stored,
    walk_in,
)

APPTS = "/api/v1/appointments"
QUEUE = f"{APPTS}/queue"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinics(session, run_id):
    """Clinic A has desk, doctor, nurse, admin and billing. Clinic B has its own people."""
    data = {label: build_clinic(session, run_id, label) for label in ("a", "b")}
    for role in ("admin", "billing"):
        create_staff(
            session,
            tenant_id=data["a"]["tenant"].id,
            email=f"a-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
    return data


def headers(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def tomorrow():
    return datetime.now(UTC) + timedelta(days=1)


def booking(clinic, **changes):
    body = {
        "patient_id": str(clinic["patient"].id),
        "branch_id": str(clinic["branch"].id),
        "clinician_id": str(clinic["doctor"].id),
        "starts_at": tomorrow().isoformat(),
    }
    return body | changes


def future_visit(session, clinic, **changes):
    """A booked visit made directly, tomorrow by the real clock."""
    return book(session, clinic, starts_at=tomorrow(), now=datetime.now(UTC), **changes)


def test_desk_books_a_visit_and_the_diary_notes_it(client, session, run_id, clinics):
    a = clinics["a"]

    response = client.post(
        APPTS, json=booking(a), headers=headers(session, run_id, "a", "front_desk")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["kind"] == "scheduled"
    assert body["patient_id"] == str(a["patient"].id)
    for hidden in ("tenant_id", "created_by_id", "created_at"):
        assert hidden not in body
    assert appointment_actions(session, a) == ["appointment.create"]


def test_clinic_sent_in_the_form_is_ignored(client, session, run_id, clinics):
    a, b = clinics["a"], clinics["b"]
    form = booking(a) | {"tenant_id": str(b["tenant"].id)}

    response = client.post(APPTS, json=form, headers=headers(session, run_id, "a", "front_desk"))

    assert response.status_code == 201
    assert len(stored(session, a)) == 1
    assert stored(session, b) == []


@pytest.mark.parametrize("role", ["admin", "billing"])
def test_admin_and_billing_cannot_use_the_appointment_doors(client, session, run_id, clinics, role):
    a = clinics["a"]
    visit = future_visit(session, a)
    h = headers(session, run_id, "a", role)
    walk_in_form = {"patient_id": str(a["patient"].id), "branch_id": str(a["branch"].id)}

    attempts = [
        client.post(APPTS, json=booking(a), headers=h),
        client.post(f"{APPTS}/walk-ins", json=walk_in_form, headers=h),
        client.get(QUEUE, params={"branch_id": str(a["branch"].id)}, headers=h),
        client.post(f"{APPTS}/{visit.id}/check-in", headers=h),
        client.post(f"{APPTS}/{visit.id}/cancel", headers=h),
        client.post(f"{APPTS}/{visit.id}/start", headers=h),
    ]

    assert [attempt.status_code for attempt in attempts] == [403] * 6
    assert len(stored(session, a)) == 1
    assert appointment_actions(session, a) == ["appointment.create"]


@pytest.mark.parametrize(
    "changes",
    [
        {"starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
        {"starts_at": "2030-01-01T09:00:00"},  # no time zone
        {"duration_minutes": 241},
        {"visit_type": "home_visit"},
    ],
)
def test_bad_bookings_get_422_and_nothing_is_saved(client, session, run_id, clinics, changes):
    a = clinics["a"]

    response = client.post(
        APPTS, json=booking(a, **changes), headers=headers(session, run_id, "a", "front_desk")
    )

    assert response.status_code == 422
    assert stored(session, a) == []
    assert appointment_actions(session, a) == []


def test_double_booking_gets_409_and_cancelling_frees_the_time(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    form = booking(a)

    first = client.post(APPTS, json=form, headers=desk)
    second = client.post(APPTS, json=form, headers=desk)

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(stored(session, a)) == 1

    assert client.post(f"{APPTS}/{first.json()['id']}/cancel", headers=desk).status_code == 200
    assert client.post(APPTS, json=form, headers=desk).status_code == 201


def test_another_clinics_references_all_look_missing_with_one_message(
    client, session, run_id, clinics
):
    a, b = clinics["a"], clinics["b"]
    desk = headers(session, run_id, "a", "front_desk")
    snoops = [
        booking(a, patient_id=str(b["patient"].id)),
        booking(a, branch_id=str(b["branch"].id)),
        booking(a, clinician_id=str(b["doctor"].id)),
        booking(a, patient_id=str(uuid.uuid4())),
    ]

    responses = [client.post(APPTS, json=snoop, headers=desk) for snoop in snoops]

    assert {response.status_code for response in responses} == {404}
    assert len({response.text for response in responses}) == 1
    assert stored(session, a) == []
    assert stored(session, b) == []


def test_a_walk_in_joins_the_queue_waiting(client, session, run_id, clinics):
    a = clinics["a"]
    form = {"patient_id": str(a["patient"].id), "branch_id": str(a["branch"].id)}

    response = client.post(
        f"{APPTS}/walk-ins", json=form, headers=headers(session, run_id, "a", "front_desk")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "walk_in"
    assert body["status"] == "waiting"
    assert body["clinician_id"] is None
    assert body["checked_in_at"] is not None


def test_a_visit_goes_through_the_doors_from_booking_to_done(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    doctor = headers(session, run_id, "a", "doctor")
    visit_id = client.post(APPTS, json=booking(a), headers=desk).json()["id"]

    checked_in = client.post(f"{APPTS}/{visit_id}/check-in", headers=desk)
    assert checked_in.status_code == 200
    assert checked_in.json()["status"] == "waiting"
    assert checked_in.json()["checked_in_at"] is not None

    # The front desk can check people in but cannot run a consultation.
    assert client.post(f"{APPTS}/{visit_id}/start", headers=desk).status_code == 403

    started = client.post(f"{APPTS}/{visit_id}/start", headers=doctor)
    assert started.status_code == 200
    assert started.json()["status"] == "in_consult"
    assert started.json()["clinician_id"] == str(a["doctor"].id)

    done = client.post(f"{APPTS}/{visit_id}/complete", headers=doctor)
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["completed_at"] is not None
    assert appointment_actions(session, a) == [
        "appointment.check_in",
        "appointment.complete",
        "appointment.create",
        "appointment.start",
    ]


def test_another_clinician_cannot_take_over_the_visit(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    nurse = headers(session, run_id, "a", "nurse")
    doctor = headers(session, run_id, "a", "doctor")
    visit_id = client.post(APPTS, json=booking(a), headers=desk).json()["id"]
    client.post(f"{APPTS}/{visit_id}/check-in", headers=desk)

    assert client.post(f"{APPTS}/{visit_id}/start", headers=nurse).status_code == 403
    assert client.post(f"{APPTS}/{visit_id}/start", headers=doctor).status_code == 200
    assert client.post(f"{APPTS}/{visit_id}/complete", headers=nurse).status_code == 403


def test_moves_the_map_forbids_get_409(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    doctor = headers(session, run_id, "a", "doctor")
    visit_id = client.post(APPTS, json=booking(a), headers=desk).json()["id"]

    assert client.post(f"{APPTS}/{visit_id}/complete", headers=doctor).status_code == 409
    client.post(f"{APPTS}/{visit_id}/check-in", headers=desk)
    client.post(f"{APPTS}/{visit_id}/start", headers=doctor)
    assert client.post(f"{APPTS}/{visit_id}/cancel", headers=desk).status_code == 409
    assert client.post(f"{APPTS}/{visit_id}/check-in", headers=desk).status_code == 409


def test_another_clinics_visit_looks_like_it_does_not_exist(client, session, run_id, clinics):
    a = clinics["a"]
    visit = future_visit(session, a)
    outsider_desk = headers(session, run_id, "b", "front_desk")
    outsider_doctor = headers(session, run_id, "b", "doctor")

    for action, who in [
        ("check-in", outsider_desk),
        ("cancel", outsider_desk),
        ("no-show", outsider_desk),
        ("start", outsider_doctor),
        ("complete", outsider_doctor),
    ]:
        snoop = client.post(f"{APPTS}/{visit.id}/{action}", headers=who)
        fake = client.post(f"{APPTS}/{uuid.uuid4()}/{action}", headers=who)
        assert snoop.status_code == 404
        assert snoop.json() == fake.json()

    form = {"starts_at": (tomorrow() + timedelta(days=1)).isoformat()}
    snoop = client.post(f"{APPTS}/{visit.id}/reschedule", json=form, headers=outsider_desk)
    fake = client.post(f"{APPTS}/{uuid.uuid4()}/reschedule", json=form, headers=outsider_desk)
    assert snoop.status_code == 404
    assert snoop.json() == fake.json()

    session.refresh(visit)
    assert visit.status == "booked"
    assert appointment_actions(session, a) == ["appointment.create"]


def test_rescheduling_through_the_door(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    first = client.post(APPTS, json=booking(a), headers=desk).json()
    later = tomorrow() + timedelta(days=2)

    moved = client.post(
        f"{APPTS}/{first['id']}/reschedule", json={"starts_at": later.isoformat()}, headers=desk
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "booked"

    # The old time is free again, and the new one is now taken.
    assert client.post(APPTS, json=booking(a), headers=desk).status_code == 201
    taken = client.post(APPTS, json=booking(a, starts_at=later.isoformat()), headers=desk)
    assert taken.status_code == 409

    naive = client.post(
        f"{APPTS}/{first['id']}/reschedule", json={"starts_at": "2030-01-01T09:00:00"}, headers=desk
    )
    assert naive.status_code == 422


def test_no_show_needs_the_start_time_to_have_passed(client, session, run_id, clinics):
    a = clinics["a"]
    desk = headers(session, run_id, "a", "front_desk")
    upcoming = future_visit(session, a)
    earlier = datetime.now(UTC) - timedelta(hours=3)
    missed = book(session, a, starts_at=earlier + timedelta(hours=1), now=earlier)

    too_early = client.post(f"{APPTS}/{upcoming.id}/no-show", headers=desk)
    on_time = client.post(f"{APPTS}/{missed.id}/no-show", headers=desk)

    assert too_early.status_code == 409
    assert on_time.status_code == 200
    assert on_time.json()["status"] == "no_show"


def test_queue_orders_the_line_hides_names_and_stays_in_one_branch(
    client, session, run_id, clinics
):
    a = clinics["a"]
    other_branch = create_branch(session, tenant_id=a["tenant"].id, name="Second branch")
    late = walk_in(session, a, now=NOW + timedelta(minutes=2))
    early = walk_in(session, a, now=NOW)
    middle = walk_in(session, a, now=NOW + timedelta(minutes=1))
    seen = walk_in(session, a, now=NOW - timedelta(minutes=5))
    not_arrived = future_visit(session, a)
    elsewhere = walk_in(session, a, branch_id=other_branch.id, now=NOW)
    start_consultation(
        session,
        tenant_id=a["tenant"].id,
        actor_id=a["doctor"].id,
        appointment_id=seen.id,
        now=NOW,
    )

    response = client.get(
        QUEUE,
        params={"branch_id": str(a["branch"].id)},
        headers=headers(session, run_id, "a", "front_desk"),
    )

    assert response.status_code == 200
    entries = response.json()
    assert [entry["appointment_id"] for entry in entries] == [
        str(visit.id) for visit in (seen, early, middle, late)
    ]
    assert [entry["status"] for entry in entries] == [
        "in_consult",
        "waiting",
        "waiting",
        "waiting",
    ]
    assert [entry["position"] for entry in entries] == [None, 1, 2, 3]
    assert str(not_arrived.id) not in response.text
    assert str(elsewhere.id) not in response.text
    assert "Test Patient" not in response.text


def test_queue_is_clinic_walled_and_noted_in_the_diary_without_naming_anyone(
    client, session, run_id, clinics
):
    a, b = clinics["a"], clinics["b"]
    walk_in(session, a)
    desk = headers(session, run_id, "a", "front_desk")
    outsider = headers(session, run_id, "b", "front_desk")
    params = {"branch_id": str(a["branch"].id)}

    client.get(QUEUE, params=params, headers=desk)
    client.get(QUEUE, params=params, headers=desk)

    lines = [
        event
        for event in list_audit_events(session, tenant_id=a["tenant"].id)
        if event.action == "queue.view"
    ]
    assert len(lines) == 2
    assert all(line.patient_id is None and line.purpose == "queue" for line in lines)

    snoop = client.get(QUEUE, params=params, headers=outsider)
    fake = client.get(QUEUE, params={"branch_id": str(uuid.uuid4())}, headers=outsider)
    assert snoop.status_code == 404
    assert snoop.json() == fake.json()
    assert [
        event
        for event in list_audit_events(session, tenant_id=b["tenant"].id)
        if event.action == "queue.view"
    ] == []