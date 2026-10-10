import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.service import create_staff, login
from app.modules.tenancy.service import create_tenant, list_branches

PASSWORD = "a-long-enough-password"
BRANCHES_URL = "/api/v1/tenancy/branches"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinic(session, run_id):
    """One clinic with an admin and a nurse."""
    tenant = create_tenant(session, name=f"Clinic {run_id}")
    staff = {}
    for role in ("admin", "nurse"):
        staff[role] = create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
    return {"tenant": tenant, "staff": staff}


def headers_for(session, run_id, name):
    token = login(session, email=f"{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_a_branch_and_then_see_it(client, session, run_id, clinic):
    headers = headers_for(session, run_id, "admin")

    created = client.post(
        BRANCHES_URL,
        json={"name": "Main branch", "city": "Test City"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Main branch"

    listing = client.get(BRANCHES_URL, headers=headers)
    assert "Main branch" in {branch["name"] for branch in listing.json()}


def test_nurse_gets_403_and_nothing_is_created(client, session, run_id, clinic):
    response = client.post(
        BRANCHES_URL,
        json={"name": "Sneaky branch"},
        headers=headers_for(session, run_id, "nurse"),
    )
    assert response.status_code == 403
    assert list_branches(session, tenant_id=clinic["tenant"].id) == []


def test_nurse_can_still_read_branches(client, session, run_id, clinic):
    response = client.get(BRANCHES_URL, headers=headers_for(session, run_id, "nurse"))
    assert response.status_code == 200


def test_blank_branch_name_is_rejected(client, session, run_id, clinic):
    response = client.post(
        BRANCHES_URL,
        json={"name": "   "},
        headers=headers_for(session, run_id, "admin"),
    )
    assert response.status_code == 422


def test_admin_cannot_create_a_branch_in_another_clinic(client, session, run_id, clinic):
    other = create_tenant(session, name=f"Other clinic {run_id}")

    response = client.post(
        BRANCHES_URL,
        json={"name": "Hijack branch", "tenant_id": str(other.id)},
        headers=headers_for(session, run_id, "admin"),
    )

    assert response.status_code == 201
    mine = {branch.name for branch in list_branches(session, tenant_id=clinic["tenant"].id)}
    theirs = list_branches(session, tenant_id=other.id)
    assert "Hijack branch" in mine
    assert theirs == []


def test_role_change_takes_effect_with_the_same_token(client, session, run_id, clinic):
    headers = headers_for(session, run_id, "nurse")
    body = {"name": "Promoted branch"}
    assert client.post(BRANCHES_URL, json=body, headers=headers).status_code == 403

    clinic["staff"]["nurse"].role = "admin"
    session.add(clinic["staff"]["nurse"])
    session.commit()

    assert client.post(BRANCHES_URL, json=body, headers=headers).status_code == 201


def test_switched_off_admin_loses_access(client, session, run_id, clinic):
    headers = headers_for(session, run_id, "admin")

    clinic["staff"]["admin"].is_active = False
    session.add(clinic["staff"]["admin"])
    session.commit()

    response = client.post(BRANCHES_URL, json={"name": "Late branch"}, headers=headers)
    assert response.status_code == 401