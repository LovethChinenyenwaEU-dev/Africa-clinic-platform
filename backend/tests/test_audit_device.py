import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.device import current_device_id, parse_device_id
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from tests.scheduling_helpers import PASSWORD, build_clinic, walk_in

WALK_INS = "/api/v1/appointments/walk-ins"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "dev")


def desk_headers(session, run_id, device=None):
    token = login(session, email=f"dev-front_desk@{run_id}.example.com", password=PASSWORD)
    result = {"Authorization": f"Bearer {token}"}
    if device is not None:
        result["X-Device-Id"] = device
    return result


def walk_in_form(clinic):
    return {"patient_id": str(clinic["patient"].id), "branch_id": str(clinic["branch"].id)}


def created_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [event for event in events if event.action == "appointment.create"]


def test_the_diary_records_which_device_a_change_came_from(client, session, run_id, clinic):
    device = uuid.uuid4()

    client.post(WALK_INS, json=walk_in_form(clinic), headers=desk_headers(session, run_id, str(device)))

    (line,) = created_lines(session, clinic)
    assert line.device_id == device


@pytest.mark.parametrize("sent", [None, "not-a-uuid", "", "DROP TABLE audit_event"])
def test_a_missing_or_malformed_device_is_recorded_as_unknown(client, session, run_id, clinic, sent):
    response = client.post(
        WALK_INS, json=walk_in_form(clinic), headers=desk_headers(session, run_id, sent)
    )

    assert response.status_code == 201  # an unknown device never blocks the work
    (line,) = created_lines(session, clinic)
    assert line.device_id is None


def test_one_requests_device_never_leaks_into_the_next(client, session, run_id, clinic):
    client.post(
        WALK_INS, json=walk_in_form(clinic), headers=desk_headers(session, run_id, str(uuid.uuid4()))
    )
    client.post(WALK_INS, json=walk_in_form(clinic), headers=desk_headers(session, run_id))

    devices = [line.device_id for line in created_lines(session, clinic)]  # newest first
    assert devices[0] is None
    assert devices[1] is not None


def test_work_done_outside_a_request_has_no_device(session, clinic):
    walk_in(session, clinic)  # called directly, like the reminder worker does

    assert current_device_id() is None
    (line,) = created_lines(session, clinic)
    assert line.device_id is None


def test_the_admin_diary_answer_includes_the_device(client, session, run_id, clinic):
    create_staff(
        session,
        tenant_id=clinic["tenant"].id,
        email=f"dev-admin@{run_id}.example.com",
        full_name="Test admin",
        role="admin",
        password=PASSWORD,
    )
    device = uuid.uuid4()
    client.post(WALK_INS, json=walk_in_form(clinic), headers=desk_headers(session, run_id, str(device)))
    admin = login(session, email=f"dev-admin@{run_id}.example.com", password=PASSWORD)

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {admin}"})

    created = [line for line in response.json() if line["action"] == "appointment.create"]
    assert created[0]["device_id"] == str(device)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"11111111-2222-4333-8444-555555555555", uuid.UUID("11111111-2222-4333-8444-555555555555")),
        ("  11111111-2222-4333-8444-555555555555 ", uuid.UUID("11111111-2222-4333-8444-555555555555")),
        (None, None),
        (b"nonsense", None),
    ],
)
def test_parse_device_id(raw, expected):
    assert parse_device_id(raw) == expected
