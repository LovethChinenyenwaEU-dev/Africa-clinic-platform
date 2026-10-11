import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.patients.models import Patient
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
PATIENTS_URL = "/api/v1/patients"


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
    """Clinic A has a front desk person, a billing person and an admin. Clinic B has its own."""
    tenant_a = create_tenant(session, name=f"Clinic A {run_id}")
    tenant_b = create_tenant(session, name=f"Clinic B {run_id}")
    return {
        "a": tenant_a,
        "b": tenant_b,
        "desk": make_person(session, tenant_a, run_id, "desk", "front_desk"),
        "billing": make_person(session, tenant_a, run_id, "billing", "billing"),
        "admin": make_person(session, tenant_a, run_id, "admin", "admin"),
        "outsider": make_person(session, tenant_b, run_id, "outsider", "front_desk"),
    }


def headers_for(session, run_id, name):
    token = login(session, email=f"{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def new_patient(**changes):
    body = {
        "full_name": "Test Patient Alpha",
        "date_of_birth": "1990-05-17",
        "sex": "female",
        "phone": "0803 123 4567",
    }
    return body | changes


def stored(session, tenant):
    return session.exec(tenant_select(Patient, tenant.id)).all()


def test_front_desk_registers_a_patient_and_the_diary_notes_it(client, session, run_id, clinics):
    response = client.post(
        PATIENTS_URL, json=new_patient(), headers=headers_for(session, run_id, "desk")
    )

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Test Patient Alpha"
    assert body["phone"] == "+2348031234567"
    assert "tenant_id" not in body
    assert "created_by_id" not in body

    events = list_audit_events(
        session, tenant_id=clinics["a"].id, patient_id=uuid.UUID(body["id"])
    )
    assert [event.action for event in events] == ["patient.create"]
    assert events[0].actor_id == clinics["desk"].id


def test_admin_cannot_register_search_or_view_patients(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "admin")

    assert client.post(PATIENTS_URL, json=new_patient(), headers=headers).status_code == 403
    assert client.get(PATIENTS_URL, params={"q": "Alpha"}, headers=headers).status_code == 403
    assert client.get(f"{PATIENTS_URL}/{uuid.uuid4()}", headers=headers).status_code == 403
    assert stored(session, clinics["a"]) == []


def test_billing_can_search_but_not_register(client, session, run_id, clinics):
    client.post(PATIENTS_URL, json=new_patient(), headers=headers_for(session, run_id, "desk"))
    billing = headers_for(session, run_id, "billing")

    assert client.post(
        PATIENTS_URL, json=new_patient(full_name="Test Patient Beta", phone=None), headers=billing
    ).status_code == 403
    searched = client.get(PATIENTS_URL, params={"q": "Alpha"}, headers=billing)
    assert searched.status_code == 200
    assert len(searched.json()) == 1
    assert len(stored(session, clinics["a"])) == 1


def test_duplicate_gets_a_409_with_ids_only_and_can_be_confirmed(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "desk")
    first = client.post(PATIENTS_URL, json=new_patient(), headers=headers)

    another = new_patient(
        full_name="Test Patient Beta", date_of_birth="2001-01-01", phone="+234 803 123 4567"
    )
    warning = client.post(PATIENTS_URL, json=another, headers=headers)

    assert warning.status_code == 409
    assert warning.json()["detail"]["matches"] == [
        {"patient_id": first.json()["id"], "reason": "same_phone"}
    ]
    assert "Test Patient" not in warning.text
    assert len(stored(session, clinics["a"])) == 1

    confirmed = client.post(
        PATIENTS_URL, json=another | {"confirmed_not_duplicate": True}, headers=headers
    )
    assert confirmed.status_code == 201
    assert len(stored(session, clinics["a"])) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": ""},
        {"full_name": "   "},
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": "1800-01-01"},
        {"date_of_birth": "not-a-date"},
        {"sex": "robot"},
        {"phone": "12345"},
    ],
)
def test_bad_details_get_422_and_nothing_is_saved(client, session, run_id, clinics, changes):
    response = client.post(
        PATIENTS_URL, json=new_patient(**changes), headers=headers_for(session, run_id, "desk")
    )

    assert response.status_code == 422
    assert stored(session, clinics["a"]) == []


def test_viewing_a_patient_works_and_is_noted(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "desk")
    created = client.post(PATIENTS_URL, json=new_patient(), headers=headers).json()

    response = client.get(f"{PATIENTS_URL}/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    events = list_audit_events(
        session, tenant_id=clinics["a"].id, patient_id=uuid.UUID(created["id"])
    )
    assert sorted(event.action for event in events) == ["patient.create", "patient.view"]


def test_another_clinics_patient_looks_like_it_does_not_exist(client, session, run_id, clinics):
    created = client.post(
        PATIENTS_URL, json=new_patient(), headers=headers_for(session, run_id, "desk")
    ).json()
    outsider = headers_for(session, run_id, "outsider")

    snooping = client.get(f"{PATIENTS_URL}/{created['id']}", headers=outsider)
    made_up = client.get(f"{PATIENTS_URL}/{uuid.uuid4()}", headers=outsider)

    assert snooping.status_code == 404
    assert snooping.status_code == made_up.status_code
    assert snooping.json() == made_up.json()
    assert list_audit_events(session, tenant_id=clinics["b"].id) == []


def test_search_finds_my_patient_and_notes_the_search_without_the_words(
    client, session, run_id, clinics
):
    headers = headers_for(session, run_id, "desk")
    client.post(PATIENTS_URL, json=new_patient(), headers=headers)

    response = client.get(PATIENTS_URL, params={"q": "alph"}, headers=headers)

    assert response.status_code == 200
    assert [patient["full_name"] for patient in response.json()] == ["Test Patient Alpha"]
    searches = [
        event
        for event in list_audit_events(session, tenant_id=clinics["a"].id)
        if event.action == "patient.search"
    ]
    assert len(searches) == 1
    assert searches[0].patient_id is None


def test_search_never_shows_another_clinics_patients(client, session, run_id, clinics):
    desk = headers_for(session, run_id, "desk")
    outsider = headers_for(session, run_id, "outsider")
    client.post(PATIENTS_URL, json=new_patient(), headers=desk)
    # The same phone in a different clinic is fine: duplicates are only checked per clinic.
    other = client.post(
        PATIENTS_URL, json=new_patient(full_name="Test Patient Outsider"), headers=outsider
    )
    assert other.status_code == 201

    response = client.get(PATIENTS_URL, params={"q": "Test Patient"}, headers=desk)

    assert [patient["full_name"] for patient in response.json()] == ["Test Patient Alpha"]


def test_short_and_wildcard_searches_do_not_list_everyone(client, session, run_id, clinics):
    headers = headers_for(session, run_id, "desk")
    client.post(PATIENTS_URL, json=new_patient(), headers=headers)

    too_short = client.get(PATIENTS_URL, params={"q": "a"}, headers=headers)
    wildcard = client.get(PATIENTS_URL, params={"q": "%%"}, headers=headers)

    assert too_short.status_code == 422
    assert wildcard.status_code == 200
    assert wildcard.json() == []


def test_clinic_sent_in_the_form_is_ignored(client, session, run_id, clinics):
    body = new_patient() | {"tenant_id": str(clinics["b"].id)}
    response = client.post(PATIENTS_URL, json=body, headers=headers_for(session, run_id, "desk"))

    assert response.status_code == 201
    assert len(stored(session, clinics["a"])) == 1
    assert stored(session, clinics["b"]) == []