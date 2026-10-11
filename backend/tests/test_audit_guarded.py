from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/audit/events"


def test_audit_route_is_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths[URL]


def test_reading_the_diary_needs_a_token():
    assert client.get(URL).status_code == 401


def test_garbage_token_is_refused():
    response = client.get(URL, headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401