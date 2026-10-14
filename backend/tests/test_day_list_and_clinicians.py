from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import (
    create_staff,
    list_active_clinicians,
    login,
    set_staff_active,
)
from app.modules.scheduling.board import get_day_list
from app.modules.scheduling.lifecycle import cancel_appointment
from app.modules.tenancy.service import create_branch
from tests.scheduling_helpers import PASSWORD, book, build_clinic, walk_in

EARLY = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)  # "now" for booking, before every visit
MONDAY = date(2026, 11, 2)


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


@pytest.fixture
def client():
    return TestClient(app)


def headers(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def day_list(session, clinic, day=MONDAY, **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "actor_id": clinic["desk"].id,
        "branch_id": clinic["branch"].id,
        "day": day,
    }
    return get_day_list(session, **(values | changes))


def at(hour_utc: int, minute: int = 0, day: int = 2) -> datetime:
    return datetime(2026, 11, day, hour_utc, minute, tzinfo=UTC)


def test_the_day_list_shows_every_visit_of_the_lagos_day_with_names(session, clinics):
    a = clinics["a"]
    late_evening = book(session, a, starts_at=at(22, 0), now=EARLY)  # 23:00 Lagos, Monday
    morning = book(session, a, starts_at=at(8, 0), now=EARLY)  # 09:00 Lagos, Monday
    cancelled = book(session, a, starts_at=at(10, 0), now=EARLY)
    cancel_appointment(
        session,
        tenant_id=a["tenant"].id,
        actor_id=a["desk"].id,
        appointment_id=cancelled.id,
        now=EARLY,
    )

    entries = day_list(session, a)

    assert [entry.appointment_id for entry in entries] == [
        morning.id,
        cancelled.id,
        late_evening.id,
    ]
    assert [entry.status for entry in entries] == ["booked", "cancelled", "booked"]
    assert {entry.patient_name for entry in entries} == {"Test Patient A"}


def test_lagos_midnight_decides_which_day_a_visit_belongs_to(session, clinics):
    a = clinics["a"]
    # 23:30 UTC on Sunday is 00:30 on Monday in Lagos: a Monday visit.
    just_after_midnight = book(session, a, starts_at=at(23, 30, day=1), now=EARLY)
    # 23:30 UTC on Monday is 00:30 on Tuesday in Lagos: not a Monday visit.
    tuesday = book(session, a, starts_at=at(23, 30, day=2), now=EARLY)

    monday_ids = [entry.appointment_id for entry in day_list(session, a)]
    tuesday_ids = [entry.appointment_id for entry in day_list(session, a, day=date(2026, 11, 3))]

    assert monday_ids == [just_after_midnight.id]
    assert tuesday_ids == [tuesday.id]


def test_the_day_list_stays_in_one_branch_and_one_clinic(session, clinics):
    a, b = clinics["a"], clinics["b"]
    other_branch = create_branch(session, tenant_id=a["tenant"].id, name="Second branch")
    here = book(session, a, starts_at=at(9), now=EARLY)
    book(session, a, starts_at=at(11), now=EARLY, branch_id=other_branch.id)
    book(session, b, starts_at=at(9), now=EARLY)

    assert [entry.appointment_id for entry in day_list(session, a)] == [here.id]


def test_each_look_at_the_day_list_is_one_diary_line_naming_nobody(session, clinics):
    a = clinics["a"]
    book(session, a, starts_at=at(9), now=EARLY)

    day_list(session, a)

    lines = [
        event
        for event in list_audit_events(session, tenant_id=a["tenant"].id)
        if event.action == "appointment.list"
    ]
    assert len(lines) == 1
    assert lines[0].patient_id is None
    assert lines[0].purpose == "day_list"


def test_the_day_list_endpoint_answers_with_names_and_hides_other_details(
    client, session, run_id, clinics
):
    a = clinics["a"]
    walk_in(session, a, now=datetime.now(UTC))
    today = (datetime.now(UTC) + timedelta(hours=1)).date()  # Lagos date

    response = client.get(
        "/api/v1/appointments/day",
        params={"branch_id": str(a["branch"].id), "date": today.isoformat()},
        headers=headers(session, run_id, "a", "front_desk"),
    )

    assert response.status_code == 200
    (entry,) = response.json()
    assert entry["patient_name"] == "Test Patient A"
    assert entry["status"] == "waiting"
    for hidden in ("tenant_id", "date_of_birth", "phone", "created_by_id"):
        assert hidden not in entry


def test_another_clinics_branch_is_not_found(client, session, run_id, clinics):
    response = client.get(
        "/api/v1/appointments/day",
        params={"branch_id": str(clinics["a"]["branch"].id), "date": "2026-11-02"},
        headers=headers(session, run_id, "b", "front_desk"),
    )

    assert response.status_code == 404


def test_a_bad_date_gets_422(client, session, run_id, clinics):
    response = client.get(
        "/api/v1/appointments/day",
        params={"branch_id": str(clinics["a"]["branch"].id), "date": "02/11/2026"},
        headers=headers(session, run_id, "a", "front_desk"),
    )

    assert response.status_code == 422


def test_only_active_doctors_and_nurses_of_this_clinic_are_listed(session, clinics, run_id):
    a = clinics["a"]
    gone = create_staff(
        session,
        tenant_id=a["tenant"].id,
        email=f"a-gone@{run_id}.example.com",
        full_name="Test Departed Doctor",
        role="doctor",
        password=PASSWORD,
    )
    set_staff_active(session, tenant_id=a["tenant"].id, staff_id=gone.id, active=False)

    clinicians = list_active_clinicians(session, tenant_id=a["tenant"].id)

    assert {person.id for person in clinicians} == {a["doctor"].id, a["nurse"].id}


def test_the_clinician_list_shows_names_and_roles_only(client, session, run_id, clinics):
    response = client.get(
        "/api/v1/staff/clinicians", headers=headers(session, run_id, "a", "front_desk")
    )

    assert response.status_code == 200
    people = response.json()
    assert {person["role"] for person in people} == {"doctor", "nurse"}
    for person in people:
        assert set(person) == {"id", "full_name", "role"}
    assert "example.com" not in response.text  # no emails


@pytest.mark.parametrize("role", ["admin", "billing"])
def test_people_who_do_not_book_visits_cannot_list_clinicians(
    client, session, run_id, clinics, role
):
    a = clinics["a"]
    create_staff(
        session,
        tenant_id=a["tenant"].id,
        email=f"a-{role}@{run_id}.example.com",
        full_name=f"Test {role}",
        role=role,
        password=PASSWORD,
    )

    response = client.get(
        "/api/v1/staff/clinicians", headers=headers(session, run_id, "a", role)
    )

    assert response.status_code == 403


def test_the_clinician_list_needs_a_token(client):
    assert client.get("/api/v1/staff/clinicians").status_code == 401
