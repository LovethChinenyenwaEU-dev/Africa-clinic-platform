import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.service import create_staff, login
from app.modules.tenancy.service import create_branch, create_tenant, get_branch, list_branches

PASSWORD = "a-long-enough-password"
BRANCHES_URL = "/api/v1/tenancy/branches"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinics(session, run_id):
    """Two separate clinics, each with one nurse and two branches."""
    data = {}
    for label in ("a", "b"):
        tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
        staff = create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{label}@{run_id}.example.com",
            full_name=f"Nurse {label.upper()}",
            role="nurse",
            password=PASSWORD,
        )
        branches = [
            create_branch(session, tenant_id=tenant.id, name=f"{label.upper()} Main"),
            create_branch(session, tenant_id=tenant.id, name=f"{label.upper()} Annex"),
        ]
        data[label] = {"tenant": tenant, "staff": staff, "branches": branches}
    return data


def headers_for(session, run_id, label):
    token = login(session, email=f"{label}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("mine,other", [("a", "b"), ("b", "a")])
def test_list_shows_only_my_clinics_branches(client, session, run_id, clinics, mine, other):
    response = client.get(BRANCHES_URL, headers=headers_for(session, run_id, mine))
    assert response.status_code == 200

    names = {branch["name"] for branch in response.json()}
    assert names == {f"{mine.upper()} Main", f"{mine.upper()} Annex"}

    other_ids = {str(branch.id) for branch in clinics[other]["branches"]}
    assert other_ids.isdisjoint({branch["id"] for branch in response.json()})


@pytest.mark.parametrize("mine,other", [("a", "b"), ("b", "a")])
def test_other_clinics_branch_looks_like_it_does_not_exist(
    client, session, run_id, clinics, mine, other
):
    headers = headers_for(session, run_id, mine)
    other_branch_id = clinics[other]["branches"][0].id

    snooping = client.get(f"{BRANCHES_URL}/{other_branch_id}", headers=headers)
    made_up = client.get(f"{BRANCHES_URL}/{uuid.uuid4()}", headers=headers)

    assert snooping.status_code == 404
    assert snooping.status_code == made_up.status_code
    assert snooping.json() == made_up.json()


def test_my_own_branch_is_readable(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "a")
    my_branch = clinics["a"]["branches"][0]

    response = client.get(f"{BRANCHES_URL}/{my_branch.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "A Main"


def test_asking_for_another_clinic_in_the_address_changes_nothing(
    client, session, run_id, clinics
):
    headers = headers_for(session, run_id, "a")
    other_tenant_id = clinics["b"]["tenant"].id

    response = client.get(f"{BRANCHES_URL}?tenant_id={other_tenant_id}", headers=headers)

    assert response.status_code == 200
    assert {branch["name"] for branch in response.json()} == {"A Main", "A Annex"}


def test_service_functions_are_scoped_too(session, clinics):
    clinic_a = clinics["a"]["tenant"].id
    clinic_b_branch = clinics["b"]["branches"][0].id

    visible_ids = {branch.id for branch in list_branches(session, tenant_id=clinic_a)}
    assert clinic_b_branch not in visible_ids
    assert get_branch(session, tenant_id=clinic_a, branch_id=clinic_b_branch) is None