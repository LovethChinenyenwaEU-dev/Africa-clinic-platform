"""Week 9 Step 3: clinicians publish weekly hours; free slots come from them (FR-C1)."""
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.scheduling.availability import (
    AvailabilityNotFoundError,
    AvailabilityOverlapError,
    InvalidAvailabilityError,
    NotAClinicianForHoursError,
    add_availability,
    free_slots,
    is_free_slot,
    list_availability,
    remove_availability,
)
from tests.scheduling_helpers import PASSWORD, book, build_clinic

MONDAY = date(2026, 11, 2)
EARLY = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)  # "now": the Friday before


def lagos(hour: int, minute: int = 0, day: date = MONDAY) -> datetime:
    """A Lagos clock time as a UTC moment (Lagos is UTC+1 all year)."""
    return datetime(day.year, day.month, day.day, hour - 1, minute, tzinfo=UTC)


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def publish(session, clinic, person="doctor", **changes):
    values = {
        "branch_id": clinic["branch"].id,
        "weekday": 0,
        "starts": time(9, 0),
        "ends": time(10, 0),
        "visit_type": "teleconsult",
        "slot_minutes": 15,
    }
    return add_availability(session, **who(clinic, person), **(values | changes))


def slots(session, clinic, visit_type="teleconsult", **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "clinician_id": clinic["doctor"].id,
        "visit_type": visit_type,
        "from_day": MONDAY,
        "days": 7,
        "now": EARLY,
    }
    return free_slots(session, **(values | changes))


def test_a_clinician_publishes_their_own_hours(session, clinics):
    clinic = clinics["a"]
    later = publish(session, clinic, weekday=2, starts=time(14, 0), ends=time(16, 0))
    earlier = publish(session, clinic)

    hours = list_availability(
        session, tenant_id=clinic["tenant"].id, clinician_id=clinic["doctor"].id
    )

    assert [row.id for row in hours] == [earlier.id, later.id]  # Monday first
    assert earlier.clinician_id == clinic["doctor"].id
    actions = [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]
    assert actions.count("availability.add") == 2


def test_front_desk_cannot_publish_hours(session, clinics):
    with pytest.raises(NotAClinicianForHoursError):
        publish(session, clinics["a"], person="desk")


@pytest.mark.parametrize(
    "changes",
    [
        {"starts": time(10, 0), "ends": time(9, 0)},
        {"starts": time(9, 0), "ends": time(9, 0)},
        {"slot_minutes": 7},
        {"visit_type": "home_visit"},
        {"weekday": 7},
    ],
)
def test_impossible_hours_are_refused(session, clinics, changes):
    with pytest.raises(InvalidAvailabilityError):
        publish(session, clinics["a"], **changes)


def test_overlapping_hours_are_refused_but_back_to_back_is_fine(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)  # Monday 09:00-10:00

    with pytest.raises(AvailabilityOverlapError):
        publish(session, clinic, starts=time(9, 30), ends=time(11, 0), visit_type="in_person")
    publish(session, clinic, starts=time(10, 0), ends=time(12, 0), visit_type="in_person")


def test_hours_are_cut_into_free_slots(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)  # Monday 09:00-10:00, 15 minutes

    found = slots(session, clinic)

    assert [slot.starts_at for slot in found] == [
        lagos(9, 0),
        lagos(9, 15),
        lagos(9, 30),
        lagos(9, 45),
    ]
    assert found[0].ends_at == lagos(9, 15)
    assert {slot.branch_id for slot in found} == {clinic["branch"].id}


def test_booked_time_past_time_and_the_other_type_are_not_offered(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)  # teleconsult 09:00-10:00
    publish(session, clinic, starts=time(10, 0), ends=time(11, 0), visit_type="in_person")
    book(session, clinic, starts_at=lagos(9, 15), duration_minutes=15, now=EARLY)

    remote = slots(session, clinic, now=lagos(9, 5))  # 09:00 has passed by then
    in_person = slots(session, clinic, visit_type="in_person")

    assert [slot.starts_at for slot in remote] == [lagos(9, 30), lagos(9, 45)]
    assert len(in_person) == 4
    assert all(slot.visit_type == "in_person" for slot in in_person)


def test_slots_repeat_every_week_inside_the_window(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)

    two_weeks = slots(session, clinic, days=14)
    one_day = slots(session, clinic, from_day=MONDAY + timedelta(days=1), days=1)

    assert len(two_weeks) == 8  # two Mondays
    assert one_day == []  # Tuesday: no hours


def test_is_free_slot_finds_exactly_that_slot(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)
    common = {
        "tenant_id": clinic["tenant"].id,
        "clinician_id": clinic["doctor"].id,
        "visit_type": "teleconsult",
        "now": EARLY,
    }

    assert is_free_slot(session, starts_at=lagos(9, 30), **common) is not None
    assert is_free_slot(session, starts_at=lagos(9, 31), **common) is None  # not on the grid
    assert is_free_slot(session, starts_at=lagos(11, 0), **common) is None  # outside hours


def test_only_your_own_hours_can_be_removed(session, clinics):
    clinic = clinics["a"]
    mine = publish(session, clinic)

    with pytest.raises(AvailabilityNotFoundError):
        remove_availability(session, **who(clinic, "nurse"), availability_id=mine.id)
    with pytest.raises(AvailabilityNotFoundError):
        remove_availability(session, **who(clinics["b"]), availability_id=mine.id)
    remove_availability(session, **who(clinic), availability_id=mine.id)

    assert slots(session, clinic) == []


def test_another_clinic_sees_no_hours(session, clinics):
    publish(session, clinics["a"])

    assert (
        list_availability(
            session, tenant_id=clinics["b"]["tenant"].id, clinician_id=clinics["a"]["doctor"].id
        )
        == []
    )


def test_hours_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    body = {
        "branch_id": str(clinic["branch"].id),
        "weekday": 0,
        "starts": "09:00",
        "ends": "10:00",
        "visit_type": "teleconsult",
        "slot_minutes": 30,
    }
    by_desk = client.post("/api/v1/availability", json=body, headers=bearer("front_desk"))
    by_nurse = client.post("/api/v1/availability", json=body, headers=bearer("nurse"))
    params = {
        "clinician_id": str(clinic["nurse"].id),
        "visit_type": "teleconsult",
        "from_day": "2026-11-02",
    }
    slots_url = "/api/v1/availability/slots"
    desk_reads = client.get(slots_url, params=params, headers=bearer("front_desk"))
    removed = client.post(
        f"/api/v1/availability/{by_nurse.json()['id']}/remove", headers=bearer("nurse")
    )

    assert by_desk.status_code == 403
    assert by_nurse.status_code == 201
    assert by_nurse.json()["clinician_id"] == str(clinic["nurse"].id)
    assert desk_reads.status_code == 200
    assert len(desk_reads.json()) == 2  # two 30-minute slots
    assert removed.status_code == 200
    assert removed.json()["id"] == by_nurse.json()["id"]
