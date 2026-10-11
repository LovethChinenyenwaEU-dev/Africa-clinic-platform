import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PATIENT = uuid.uuid4()
CONSENTS = f"/api/v1/patients/{PATIENT}/consents"

DOORS = [
    ("post", "/api/v1/consent/texts", {"json": {"purpose": "treatment", "body": "I agree."}}),
    ("get", "/api/v1/consent/texts/current", {"params": {"purpose": "treatment"}}),
    ("post", CONSENTS, {"json": {"purpose": "treatment", "granted_by": "patient"}}),
    ("get", CONSENTS, {}),
    ("post", f"{CONSENTS}/treatment/revoke", {}),
]


def test_consent_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/api/v1/consent/texts"]
    assert "get" in paths["/api/v1/consent/texts/current"]
    assert {"get", "post"} <= set(paths["/api/v1/patients/{patient_id}/consents"])
    assert "post" in paths["/api/v1/patients/{patient_id}/consents/{purpose}/revoke"]


@pytest.mark.parametrize("method,url,extras", DOORS)
def test_every_consent_door_needs_a_token(method, url, extras):
    assert client.request(method, url, **extras).status_code == 401


def test_garbage_token_is_refused():
    response = client.get(CONSENTS, headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401