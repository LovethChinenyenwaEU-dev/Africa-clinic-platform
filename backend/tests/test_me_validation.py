import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.tokens import create_access_token

client = TestClient(app)
ME_URL = "/api/v1/auth/me"


def test_me_route_is_registered():
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths[ME_URL]


def test_no_token_gets_401():
    response = client.get(ME_URL)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated."}


def test_garbage_token_gets_401():
    response = client.get(ME_URL, headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401


def test_wrong_kind_of_credentials_gets_401():
    response = client.get(ME_URL, headers={"Authorization": "Basic YTpi"})
    assert response.status_code == 401


def test_expired_token_gets_401():
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(
        staff_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role="nurse",
        now=two_hours_ago,
    )
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401