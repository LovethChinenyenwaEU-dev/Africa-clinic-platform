from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/api/v1/tenancy/branches"


def test_creating_a_branch_needs_a_token():
    assert client.post(URL, json={"name": "Main branch"}).status_code == 401


def test_garbage_token_cannot_create_a_branch():
    response = client.post(
        URL,
        json={"name": "Main branch"},
        headers={"Authorization": "Bearer nonsense"},
    )
    assert response.status_code == 401