import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
APPTS = "/api/v1/appointments"
ID = uuid.uuid4()
BRANCH = str(uuid.uuid4())
WHEN = "2030-01-01T09:00:00+00:00"

BOOKING = {
    "patient_id": str(uuid.uuid4()),
    "branch_id": BRANCH,
    "clinician_id": str(uuid.uuid4()),
    "starts_at": WHEN,
}
WALK_IN = {"patient_id": str(uuid.uuid4()), "branch_id": BRANCH}

DOORS = [
    ("post", APPTS, {"json": BOOKING}),
    ("post", f"{APPTS}/walk-ins", {"json": WALK_IN}),
    ("get", f"{APPTS}/queue", {"params": {"branch_id": BRANCH}}),
    ("post", f"{APPTS}/{ID}/check-in", {}),
    ("post", f"{APPTS}/{ID}/start", {}),
    ("post", f"{APPTS}/{ID}/complete", {}),
    ("post", f"{APPTS}/{ID}/cancel", {}),
    ("post", f"{APPTS}/{ID}/no-show", {}),
    ("post", f"{APPTS}/{ID}/reschedule", {"json": {"starts_at": WHEN}}),
]


def test_appointment_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]
    for _, url, _ in DOORS:
        template = url.replace(str(ID), "{appointment_id}")
        assert template in paths


@pytest.mark.parametrize("method,url,extras", DOORS)
def test_every_appointment_door_needs_a_token(method, url, extras):
    assert client.request(method, url, **extras).status_code == 401


def test_garbage_token_is_refused():
    response = client.get(
        f"{APPTS}/queue", params={"branch_id": BRANCH}, headers={"Authorization": "Bearer nonsense"}
    )
    assert response.status_code == 401