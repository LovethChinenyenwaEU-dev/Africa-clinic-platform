from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
LOGIN_URL = "/api/v1/auth/login"


def test_login_route_is_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert LOGIN_URL in paths
    assert "post" in paths[LOGIN_URL]


def test_missing_body_is_rejected():
    assert client.post(LOGIN_URL).status_code == 422


def test_empty_fields_are_rejected():
    response = client.post(LOGIN_URL, json={"email": "", "password": ""})
    assert response.status_code == 422


def test_giant_password_is_rejected_before_any_hashing():
    response = client.post(LOGIN_URL, json={"email": "a@example.com", "password": "x" * 129})
    assert response.status_code == 422