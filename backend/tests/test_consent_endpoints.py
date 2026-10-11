import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.models import Consent, ConsentText
from app.modules.consent.service import has_active_consent
from app.modules.identity.service import create_staff, login
from app.modules.patients.service import create_patient
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
TEXTS_URL = "/api/v1/consent/texts"
CURRENT_URL = f"{TEXTS_URL}/current"


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
    """Clinic A: admin, front desk, billing and one patient. Clinic B: its own desk and patient."""
    tenant_a = create_tenant(session, name=f"Clinic A {run_id}")
    tenant_b = create_tenant(session, name=f"Clinic B {run_id}")
    desk = make_person(session, tenant_a, run_id, "desk", "front_desk")
    outsider = make_person(session, tenant_b, run_id, "outsider", "front_desk")
    make_person(session, tenant_a, run_id, "admin", "admin")
    make_person(session, tenant_a, run_id, "billing", "billing")
    return {
        "a": tenant_a,
        "b": tenant_b,
        "desk": desk,
        "patient": create_patient(
            session,
            tenant_id=tenant_a.id,
            actor_id=desk.id,
            full_name="Test Patient Alpha",
            date_of_birth=date(1990, 5, 17),
            sex="female",
        ),
        "other_patient": create_patient(
            session,
            tenant_id=tenant_b.id,
            actor_id=outsider.id,
            full_name="Test Patient Beta",
            date_of_birth=date(1991, 6, 18),
            sex="male",
        ),
    }


def headers_for(session, run_id, name):
    token = login(session, email=f"{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def consents_url(patient_id):
    return f"/api/v1/patients/{patient_id}/consents"


def publish(client, headers, *, purpose="treatment", body="I agree to treatment."):
    return client.post(TEXTS_URL, json={"purpose": purpose, "body": body}, headers=headers)


def record(client, headers, patient_id, *, purpose="treatment", granted_by="patient"):
    payload = {"purpose": purpose, "granted_by": granted_by}
    return client.post(consents_url(patient_id), json=payload, headers=headers)


def revoke(client, headers, patient_id, purpose="treatment"):
    return client.post(f"{consents_url(patient_id)}/{purpose}/revoke", headers=headers)


def stored_texts(session, tenant):
    return session.exec(tenant_select(ConsentText, tenant.id)).all()


def stored_consents(session, tenant):
    return session.exec(tenant_select(Consent, tenant.id)).all()


def consent_actions(session, tenant, patient_id=None):
    events = list_audit_events(session, tenant_id=tenant.id, patient_id=patient_id)
    return sorted(event.action for event in events if event.action.startswith("consent."))


def is_active(session, clinics):
    return has_active_consent(
        session,
        tenant_id=clinics["a"].id,
        patient_id=clinics["patient"].id,
        purpose="treatment",
    )


def test_admin_publishes_wording_and_front_line_staff_read_the_newest(
    client, session, run_id, clinics
):
    admin = headers_for(session, run_id, "admin")
    desk = headers_for(session, run_id, "desk")

    first = publish(client, admin, body="First wording.")
    second = publish(client, admin, body="Second wording.")

    assert first.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2

    current = client.get(CURRENT_URL, params={"purpose": "treatment"}, headers=desk)
    assert current.status_code == 200
    assert current.json()["version"] == 2
    assert current.json()["body"] == "Second wording."
    assert "tenant_id" not in current.json()
    assert "created_by_id" not in current.json()
    assert len(stored_texts(session, clinics["a"])) == 2


def test_only_admins_publish_wording_and_billing_cannot_read_it(client, session, run_id, clinics):
    for name in ("desk", "billing"):
        assert publish(client, headers_for(session, run_id, name)).status_code == 403
    assert stored_texts(session, clinics["a"]) == []

    publish(client, headers_for(session, run_id, "admin"))
    params = {"purpose": "treatment"}
    billing = client.get(CURRENT_URL, params=params, headers=headers_for(session, run_id, "billing"))
    assert billing.status_code == 403
    for name in ("admin", "desk"):
        allowed = client.get(CURRENT_URL, params=params, headers=headers_for(session, run_id, name))
        assert allowed.status_code == 200


def test_wording_that_does_not_exist_or_has_an_unknown_purpose(client, session, run_id, clinics):
    desk = headers_for(session, run_id, "desk")

    missing = client.get(CURRENT_URL, params={"purpose": "treatment"}, headers=desk)
    unknown = client.get(CURRENT_URL, params={"purpose": "wizardry"}, headers=desk)

    assert missing.status_code == 404
    assert unknown.status_code == 422


@pytest.mark.parametrize(
    "changes",
    [{"body": "   "}, {"body": "x" * 5001}, {"purpose": "wizardry"}],
)
def test_bad_wording_gets_422_and_nothing_is_saved(client, session, run_id, clinics, changes):
    payload = {"purpose": "treatment", "body": "I agree."} | changes

    response = client.post(TEXTS_URL, json=payload, headers=headers_for(session, run_id, "admin"))

    assert response.status_code == 422
    assert stored_texts(session, clinics["a"]) == []


def test_desk_records_consent_and_the_diary_notes_it(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    desk = headers_for(session, run_id, "desk")

    response = record(client, desk, clinics["patient"].id, granted_by="caregiver")

    assert response.status_code == 201
    body = response.json()
    assert body["purpose"] == "treatment"
    assert body["wording_version"] == 1
    assert body["granted_by"] == "caregiver"
    assert body["revoked_at"] is None
    for hidden in ("tenant_id", "recorded_by_id", "revoked_by_id", "consent_text_id"):
        assert hidden not in body

    events = [
        event
        for event in list_audit_events(
            session, tenant_id=clinics["a"].id, patient_id=clinics["patient"].id
        )
        if event.action == "consent.grant"
    ]
    assert len(events) == 1
    assert events[0].purpose == "treatment"
    assert events[0].actor_id == clinics["desk"].id


def test_recording_before_any_wording_gets_409_and_saves_nothing(client, session, run_id, clinics):
    response = record(client, headers_for(session, run_id, "desk"), clinics["patient"].id)

    assert response.status_code == 409
    assert stored_consents(session, clinics["a"]) == []
    assert consent_actions(session, clinics["a"], clinics["patient"].id) == []


def test_recording_twice_returns_the_same_consent(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    desk = headers_for(session, run_id, "desk")

    first = record(client, desk, clinics["patient"].id)
    second = record(client, desk, clinics["patient"].id)

    assert first.json()["id"] == second.json()["id"]
    assert len(stored_consents(session, clinics["a"])) == 1


@pytest.mark.parametrize("changes", [{"purpose": "wizardry"}, {"granted_by": "stranger"}])
def test_bad_consent_details_get_422_and_nothing_is_saved(client, session, run_id, clinics, changes):
    publish(client, headers_for(session, run_id, "admin"))
    payload = {"purpose": "treatment", "granted_by": "patient"} | changes

    response = client.post(
        consents_url(clinics["patient"].id),
        json=payload,
        headers=headers_for(session, run_id, "desk"),
    )

    assert response.status_code == 422
    assert stored_consents(session, clinics["a"]) == []
    assert consent_actions(session, clinics["a"], clinics["patient"].id) == []


def test_admin_and_billing_cannot_touch_consent_records(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    record(client, headers_for(session, run_id, "desk"), clinics["patient"].id)
    patient_id = clinics["patient"].id

    for name in ("admin", "billing"):
        headers = headers_for(session, run_id, name)
        assert record(client, headers, patient_id).status_code == 403
        assert client.get(consents_url(patient_id), headers=headers).status_code == 403
        assert revoke(client, headers, patient_id).status_code == 403

    assert is_active(session, clinics)


def test_another_clinics_patient_looks_like_it_does_not_exist(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    outsider = headers_for(session, run_id, "outsider")
    made_up = uuid.uuid4()
    mine = clinics["patient"].id

    record_snoop = record(client, outsider, mine)
    record_fake = record(client, outsider, made_up)
    list_snoop = client.get(consents_url(mine), headers=outsider)
    list_fake = client.get(consents_url(made_up), headers=outsider)

    assert record_snoop.status_code == 404
    assert record_snoop.json() == record_fake.json()
    assert list_snoop.status_code == 404
    assert list_snoop.json() == list_fake.json()
    assert stored_consents(session, clinics["a"]) == []
    assert stored_consents(session, clinics["b"]) == []
    assert consent_actions(session, clinics["b"]) == []


def test_another_clinic_cannot_revoke_my_consent(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    record(client, headers_for(session, run_id, "desk"), clinics["patient"].id)
    outsider = headers_for(session, run_id, "outsider")

    snoop = revoke(client, outsider, clinics["patient"].id)
    fake = revoke(client, outsider, uuid.uuid4())

    assert snoop.status_code == 404
    assert snoop.json() == fake.json()
    assert is_active(session, clinics)


def test_history_keeps_old_wording_revoking_keeps_the_record_and_regranting_uses_newest(
    client, session, run_id, clinics
):
    admin = headers_for(session, run_id, "admin")
    desk = headers_for(session, run_id, "desk")
    patient_id = clinics["patient"].id

    publish(client, admin, body="Old wording.")
    record(client, desk, patient_id)
    publish(client, admin, body="New wording.")

    unchanged = client.get(consents_url(patient_id), headers=desk).json()
    assert [item["wording_version"] for item in unchanged] == [1]

    revoked = revoke(client, desk, patient_id)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert revoked.json()["wording_version"] == 1
    assert not is_active(session, clinics)
    assert revoke(client, desk, patient_id).status_code == 404

    again = record(client, desk, patient_id)
    assert again.status_code == 201
    assert again.json()["wording_version"] == 2

    history = client.get(consents_url(patient_id), headers=desk).json()
    assert [item["wording_version"] for item in history] == [2, 1]
    assert history[0]["revoked_at"] is None
    assert history[1]["revoked_at"] is not None
    assert len(stored_consents(session, clinics["a"])) == 2
    assert consent_actions(session, clinics["a"], patient_id) == [
        "consent.grant",
        "consent.grant",
        "consent.revoke",
        "consent.view",
        "consent.view",
    ]


def test_revoking_an_unknown_purpose_gets_422(client, session, run_id, clinics):
    response = revoke(
        client, headers_for(session, run_id, "desk"), clinics["patient"].id, purpose="wizardry"
    )
    assert response.status_code == 422


def test_clinic_sent_in_the_form_is_ignored(client, session, run_id, clinics):
    publish(client, headers_for(session, run_id, "admin"))
    payload = {"purpose": "treatment", "granted_by": "patient", "tenant_id": str(clinics["b"].id)}

    response = client.post(
        consents_url(clinics["patient"].id),
        json=payload,
        headers=headers_for(session, run_id, "desk"),
    )

    assert response.status_code == 201
    assert len(stored_consents(session, clinics["a"])) == 1
    assert stored_consents(session, clinics["b"]) == []