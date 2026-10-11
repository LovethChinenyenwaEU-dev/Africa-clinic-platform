import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/patients"
BODY = {"full_name": "Test Patient Alpha", "date_of_birth": "1990-05-17", "sex": "female"}


def test_patient_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert {"get", "post"} <= set(paths[URL])
    assert "get" in paths[f"{URL}/{{patient_id}}"]


def test_registering_needs_a_token():
    assert client.post(URL, json=BODY).status_code == 401


def test_searching_needs_a_token():
    assert client.get(URL, params={"q": "alpha"}).status_code == 401


def test_viewing_needs_a_token():
    assert client.get(f"{URL}/{uuid.uuid4()}").status_code == 401


def test_garbage_token_is_refused():
    response = client.post(URL, json=BODY, headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401