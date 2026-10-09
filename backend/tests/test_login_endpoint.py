import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.service import create_staff
from app.modules.identity.tokens import decode_access_token
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def account(session, run_id):
    tenant = create_tenant(session, name=f"Clinic {run_id}")
    return create_staff(
        session,
        tenant_id=tenant.id,
        email=f"nurse@{run_id}.example.com",
        full_name="Test Nurse",
        role="nurse",
        password=PASSWORD,
    )


def test_login_returns_a_bearer_token(client, run_id, account):
    response = client.post(
        LOGIN_URL,
        json={"email": f"nurse@{run_id}.example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]).staff_id == account.id


def test_wrong_password_gets_401_and_no_token(client, run_id, account):
    response = client.post(
        LOGIN_URL,
        json={"email": f"nurse@{run_id}.example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_email_gets_the_exact_same_answer(client, run_id, account):
    wrong_password = client.post(
        LOGIN_URL,
        json={"email": f"nurse@{run_id}.example.com", "password": "not-the-password"},
    )
    unknown_email = client.post(
        LOGIN_URL,
        json={"email": f"nobody@{run_id}.example.com", "password": PASSWORD},
    )
    assert unknown_email.status_code == wrong_password.status_code
    assert unknown_email.json() == wrong_password.json()