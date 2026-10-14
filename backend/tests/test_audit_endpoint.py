from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.patients.service import create_patient
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
EVENTS_URL = "/api/v1/audit/events"


@pytest.fixture
def client():
    return TestClient(app)


def make_person(session, tenant, run_id, name, role):
    return create_staff(
        session,
        tenant_id=tenant.id,
        email=f"{name}@{run_id}.example.com",
        full_name=f"Test {name}",
        role=role,
        password=PASSWORD,
    )


@pytest.fixture
def clinics(session, run_id):
    """Clinic A: admin, desk, nurse, billing and one patient. Clinic B: its own admin."""
    tenant_a = create_tenant(session, name=f"Clinic A {run_id}")
    tenant_b = create_tenant(session, name=f"Clinic B {run_id}")
    desk = make_person(session, tenant_a, run_id, "desk", "front_desk")
    admin = make_person(session, tenant_a, run_id, "admin", "admin")
    make_person(session, tenant_a, run_id, "nurse", "nurse")
    make_person(session, tenant_a, run_id, "billing", "billing")
    make_person(session, tenant_b, run_id, "outsider_admin", "admin")
    patient = create_patient(
        session,
        tenant_id=tenant_a.id,
        actor_id=desk.id,
        full_name="Test Patient Alpha",
        date_of_birth=date(1990, 5, 17),
        sex="female",
    )
    return {"a": tenant_a, "b": tenant_b, "desk": desk, "admin": admin, "patient": patient}


def headers_for(session, run_id, name):
    token = login(session, email=f"{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_admin_sees_what_staff_did_but_no_personal_details(client, session, run_id, clinics):
    response = client.get(EVENTS_URL, headers=headers_for(session, run_id, "admin"))

    assert response.status_code == 200
    created = [event for event in response.json() if event["action"] == "patient.create"]
    assert len(created) == 1
    assert created[0]["actor_id"] == str(clinics["desk"].id)
    assert created[0]["patient_id"] == str(clinics["patient"].id)
    assert "tenant_id" not in created[0]
    assert "Test Patient" not in response.text


def test_reading_the_diary_is_itself_written_in_the_diary(client, session, run_id, clinics):
    admin = headers_for(session, run_id, "admin")

    client.get(EVENTS_URL, headers=admin)
    second = client.get(EVENTS_URL, headers=admin)

    views = [event for event in second.json() if event["action"] == "audit.view"]
    assert len(views) == 2
    assert {view["actor_id"] for view in views} == {str(clinics["admin"].id)}


def test_admin_can_filter_the_diary_by_patient(client, session, run_id, clinics):
    create_patient(
        session,
        tenant_id=clinics["a"].id,
        actor_id=clinics["desk"].id,
        full_name="Test Patient Beta",
        date_of_birth=date(1985, 1, 1),
        sex="male",
    )
    patient_id = str(clinics["patient"].id)

    response = client.get(
        EVENTS_URL, params={"patient_id": patient_id}, headers=headers_for(session, run_id, "admin")
    )

    assert response.status_code == 200
    assert {event["patient_id"] for event in response.json()} == {patient_id}


@pytest.mark.parametrize("name", ["desk", "nurse", "billing"])
def test_only_admins_can_read_the_diary(client, session, run_id, clinics, name):
    response = client.get(EVENTS_URL, headers=headers_for(session, run_id, name))

    assert response.status_code == 403
    events = list_audit_events(session, tenant_id=clinics["a"].id)
    assert [event for event in events if event.action == "audit.view"] == []


def test_another_clinics_admin_sees_none_of_my_diary(client, session, run_id, clinics):
    response = client.get(EVENTS_URL, headers=headers_for(session, run_id, "outsider_admin"))

    assert response.status_code == 200
    assert [event["action"] for event in response.json()] == ["audit.view"]
    assert str(clinics["patient"].id) not in response.text


@pytest.mark.parametrize("limit", [0, -5, 201])
def test_silly_page_sizes_get_422(client, session, run_id, clinics, limit):
    response = client.get(
        EVENTS_URL, params={"limit": limit}, headers=headers_for(session, run_id, "admin")
    )
    assert response.status_code == 422


def test_limit_trims_the_answer(client, session, run_id, clinics):
    response = client.get(
        EVENTS_URL, params={"limit": 1}, headers=headers_for(session, run_id, "admin")
    )

    assert response.status_code == 200
    assert len(response.json()) == 1

def test_admin_can_filter_the_diary_by_staff_member(client, session, run_id, clinics):
    desk_id = str(clinics["desk"].id)

    response = client.get(
        EVENTS_URL, params={"staff_id": desk_id}, headers=headers_for(session, run_id, "admin")
    )

    assert response.status_code == 200
    assert response.json()  # the desk registered the patient
    assert {event["actor_id"] for event in response.json()} == {desk_id}


def test_admin_can_filter_the_diary_by_time(client, session, run_id, clinics):
    admin = headers_for(session, run_id, "admin")
    now = datetime.now(UTC)

    recent = client.get(
        EVENTS_URL, params={"since": (now - timedelta(hours=1)).isoformat()}, headers=admin
    )
    long_ago = client.get(
        EVENTS_URL, params={"until": (now - timedelta(days=30)).isoformat()}, headers=admin
    )

    assert recent.status_code == long_ago.status_code == 200
    assert "patient.create" in [event["action"] for event in recent.json()]
    assert long_ago.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"since": "2026-10-14T00:00:00"},  # no time zone
        {"since": "2026-10-14T00:00:00+00:00", "until": "2026-10-13T00:00:00+00:00"},
        {"staff_id": "not-an-id"},
    ],
)
def test_bad_filters_get_422_and_are_not_logged(client, session, run_id, clinics, params):
    response = client.get(EVENTS_URL, params=params, headers=headers_for(session, run_id, "admin"))

    assert response.status_code == 422
    events = list_audit_events(session, tenant_id=clinics["a"].id)
    assert [event for event in events if event.action == "audit.view"] == []
