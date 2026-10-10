import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
STAFF_URL = "/api/v1/staff"
SOME_BODY = {
    "email": "someone@example.com",
    "full_name": "Some One",
    "role": "nurse",
    "password": "a-long-enough-password",
}


def test_listing_staff_needs_a_token():
    assert client.get(STAFF_URL).status_code == 401


def test_adding_staff_needs_a_token():
    assert client.post(STAFF_URL, json=SOME_BODY).status_code == 401


@pytest.mark.parametrize("action", ["activate", "deactivate"])
def test_switching_staff_needs_a_token(action):
    assert client.post(f"{STAFF_URL}/{uuid.uuid4()}/{action}").status_code == 401


def test_garbage_token_is_refused():
    response = client.get(STAFF_URL, headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401