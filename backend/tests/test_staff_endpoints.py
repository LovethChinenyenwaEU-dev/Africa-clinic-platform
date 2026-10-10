import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.service import create_staff, login
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
STAFF_URL = "/api/v1/staff"
ME_URL = "/api/v1/auth/me"


@pytest.fixture
def client():
    return TestClient(app)


def make_person(session, tenant, run_id, name, role):
    return create_staff(
        session,
        tenant_id=tenant.id,
        email=f"{name}@{run_id}.example.com",
        full_name=f"Test {name}",
        role=role,
        password=PASSWORD,
    )


@pytest.fixture
def clinics(session, run_id):
    """Clinic A has an admin and a nurse. Clinic B has its own admin."""
    tenant_a = create_tenant(session, name=f"Clinic A {run_id}")
    tenant_b = create_tenant(session, name=f"Clinic B {run_id}")
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin": make_person(session, tenant_a, run_id, "admin", "admin"),
        "nurse": make_person(session, tenant_a, run_id, "nurse", "nurse"),
        "outsider": make_person(session, tenant_b, run_id, "outsider", "admin"),
    }


def headers_for(session, run_id, name):
    token = login(session, email=f"{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def new_person(run_id, name="newhire", role="nurse", password=PASSWORD):
    return {
        "email": f"{name}@{run_id}.example.com",
        "full_name": "New Hire",
        "role": role,
        "password": password,
    }


def test_admin_adds_a_nurse_who_can_then_log_in(client, session, run_id, clinics):
    response = client.post(
        STAFF_URL, json=new_person(run_id), headers=headers_for(session, run_id, "admin")
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "nurse"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body

    token = login(session, email=f"newhire@{run_id}.example.com", password=PASSWORD)
    me = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["tenant_id"] == str(clinics["tenant_a"].id)


def test_nurse_cannot_add_staff_and_nothing_is_created(client, session, run_id, clinics):
    nurse_attempt = client.post(
        STAFF_URL, json=new_person(run_id), headers=headers_for(session, run_id, "nurse")
    )
    assert nurse_attempt.status_code == 403

    listing = client.get(STAFF_URL, headers=headers_for(session, run_id, "admin"))
    emails = {person["email"] for person in listing.json()}
    assert f"newhire@{run_id}.example.com" not in emails


def test_nurse_cannot_list_staff(client, session, run_id, clinics):
    response = client.get(STAFF_URL, headers=headers_for(session, run_id, "nurse"))
    assert response.status_code == 403


def test_admin_sees_only_their_own_clinics_staff(client, session, run_id, clinics):
    response = client.get(STAFF_URL, headers=headers_for(session, run_id, "admin"))
    assert response.status_code == 200
    emails = {person["email"] for person in response.json()}
    assert emails == {f"admin@{run_id}.example.com", f"nurse@{run_id}.example.com"}


def test_duplicate_email_gets_409_even_with_different_capitals(client, session, run_id, clinics):
    body = new_person(run_id, name="nurse").copy()
    body["email"] = f"NURSE@{run_id}.EXAMPLE.COM"
    response = client.post(STAFF_URL, json=body, headers=headers_for(session, run_id, "admin"))
    assert response.status_code == 409


def test_weak_password_and_unknown_role_get_422(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "admin")
    weak = client.post(STAFF_URL, json=new_person(run_id, password="short"), headers=headers)
    wizard = client.post(STAFF_URL, json=new_person(run_id, role="wizard"), headers=headers)
    assert weak.status_code == 422
    assert wizard.status_code == 422


def test_clinic_sent_in_the_form_is_ignored(client, session, run_id, clinics):
    body = new_person(run_id) | {"tenant_id": str(clinics["tenant_b"].id)}
    created = client.post(STAFF_URL, json=body, headers=headers_for(session, run_id, "admin"))
    assert created.status_code == 201

    clinic_b_listing = client.get(STAFF_URL, headers=headers_for(session, run_id, "outsider"))
    emails = {person["email"] for person in clinic_b_listing.json()}
    assert emails == {f"outsider@{run_id}.example.com"}


def test_switching_a_nurse_off_stops_her_existing_token_and_on_restores_it(
    client, session, run_id, clinics
):
    admin_headers = headers_for(session, run_id, "admin")
    nurse_headers = headers_for(session, run_id, "nurse")
    nurse_id = clinics["nurse"].id
    assert client.get(ME_URL, headers=nurse_headers).status_code == 200

    off = client.post(f"{STAFF_URL}/{nurse_id}/deactivate", headers=admin_headers)
    assert off.status_code == 200
    assert off.json()["is_active"] is False
    assert client.get(ME_URL, headers=nurse_headers).status_code == 401

    on = client.post(f"{STAFF_URL}/{nurse_id}/activate", headers=admin_headers)
    assert on.status_code == 200
    assert client.get(ME_URL, headers=nurse_headers).status_code == 200


def test_another_clinics_staff_looks_like_they_do_not_exist(client, session, run_id, clinics):
    admin_headers = headers_for(session, run_id, "admin")
    outsider_id = clinics["outsider"].id

    snooping = client.post(f"{STAFF_URL}/{outsider_id}/deactivate", headers=admin_headers)
    made_up = client.post(f"{STAFF_URL}/{uuid.uuid4()}/deactivate", headers=admin_headers)
    assert snooping.status_code == 404
    assert snooping.status_code == made_up.status_code
    assert snooping.json() == made_up.json()

    still_works = client.get(ME_URL, headers=headers_for(session, run_id, "outsider"))
    assert still_works.status_code == 200


def test_the_last_active_admin_cannot_be_switched_off(client, session, run_id, clinics):
    admin_headers = headers_for(session, run_id, "admin")
    response = client.post(f"{STAFF_URL}/{clinics['admin'].id}/deactivate", headers=admin_headers)
    assert response.status_code == 409
    assert client.get(ME_URL, headers=admin_headers).status_code == 200


def test_an_admin_can_be_switched_off_when_another_admin_remains(client, session, run_id, clinics):
    second_admin = make_person(session, clinics["tenant_a"], run_id, "admin2", "admin")
    response = client.post(
        f"{STAFF_URL}/{second_admin.id}/deactivate",
        headers=headers_for(session, run_id, "admin"),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False