import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_branch_list_needs_a_token():
    assert client.get("/api/v1/tenancy/branches").status_code == 401


def test_single_branch_needs_a_token():
    assert client.get(f"/api/v1/tenancy/branches/{uuid.uuid4()}").status_code == 401


def test_garbage_token_is_refused():
    response = client.get(
        "/api/v1/tenancy/branches",
        headers={"Authorization": "Bearer nonsense"},
    )
    assert response.status_code == 401