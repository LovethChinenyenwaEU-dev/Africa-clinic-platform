import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
API = "/api/v1"
ID = uuid.uuid4()
PATIENT = str(uuid.uuid4())
MEDICINE = {"medicine": "Paracetamol", "dose": "1 g", "frequency": "8-hourly", "duration": "3 days"}

DOORS = [
    ("post", f"{API}/encounters", {"json": {"patient_id": PATIENT}}),
    ("get", f"{API}/encounters/{ID}", {}),
    ("post", f"{API}/encounters/{ID}/close", {}),
    ("post", f"{API}/encounters/{ID}/entered-in-error", {}),
    ("get", f"{API}/patients/{ID}/encounters", {}),
    ("post", f"{API}/encounters/{ID}/vitals", {"json": {"pulse_bpm": 80}}),
    ("get", f"{API}/encounters/{ID}/vitals", {}),
    ("post", f"{API}/vitals/{ID}/corrections", {"json": {"pulse_bpm": 80}}),
    ("post", f"{API}/encounters/{ID}/allergies", {"json": {"substance": "Penicillin"}}),
    (
        "post",
        f"{API}/allergies/{ID}/revisions",
        {"json": {"substance": "Penicillin", "encounter_id": str(ID)}},
    ),
    ("get", f"{API}/patients/{ID}/allergies", {}),
    ("post", f"{API}/encounters/{ID}/problems", {"json": {"description": "Malaria"}}),
    (
        "post",
        f"{API}/problems/{ID}/revisions",
        {"json": {"description": "Malaria", "encounter_id": str(ID)}},
    ),
    ("get", f"{API}/patients/{ID}/problems", {}),
    ("post", f"{API}/encounters/{ID}/notes", {"json": {"kind": "history", "body": "x"}}),
    ("post", f"{API}/notes/{ID}/amendments", {"json": {"body": "x"}}),
    ("get", f"{API}/encounters/{ID}/notes", {}),
    ("post", f"{API}/vitals/{ID}/resolve", {"json": {"keep": "this"}}),
    ("post", f"{API}/allergies/{ID}/resolve", {"json": {"keep": "this"}}),
    ("post", f"{API}/problems/{ID}/resolve", {"json": {"keep": "this"}}),
    ("post", f"{API}/notes/{ID}/resolve", {"json": {"keep": "this"}}),
    ("post", f"{API}/encounters/{ID}/prescriptions", {"json": MEDICINE}),
    ("get", f"{API}/encounters/{ID}/prescriptions", {}),
    ("post", f"{API}/prescriptions/{ID}/revisions", {"json": MEDICINE}),
    ("post", f"{API}/prescriptions/{ID}/resolve", {"json": {"keep": "this"}}),
    ("post", f"{API}/encounters/{ID}/follow-ups", {"json": {"due_date": "2026-12-01"}}),
    ("get", f"{API}/encounters/{ID}/follow-ups", {}),
    ("get", f"{API}/follow-ups/due", {"params": {"until": "2026-12-01"}}),
    ("post", f"{API}/follow-ups/{ID}/booked", {"json": {}}),
    ("post", f"{API}/follow-ups/{ID}/cancel", {}),
    ("post", f"{API}/encounters/{ID}/referrals", {"json": {"to_name": "X", "reason": "Y"}}),
    ("get", f"{API}/encounters/{ID}/referrals", {}),
    ("get", f"{API}/referrals/{ID}", {}),
    ("post", f"{API}/referrals/{ID}/cancel", {}),
]


def test_records_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]
    templates = {
        "encounters": "{encounter_id}",
        "patients": "{patient_id}",
        "vitals": "{vitals_id}",
        "allergies": "{allergy_id}",
        "problems": "{problem_id}",
        "notes": "{note_id}",
        "prescriptions": "{prescription_id}",
        "follow-ups": "{follow_up_id}",
        "referrals": "{referral_id}",
    }
    for _, url, _ in DOORS:
        resource = url.removeprefix(f"{API}/").split("/")[0]
        assert url.replace(str(ID), templates[resource]) in paths


@pytest.mark.parametrize("method,url,extras", DOORS)
def test_every_records_door_needs_a_token(method, url, extras):
    assert client.request(method, url, **extras).status_code == 401
