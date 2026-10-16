"""Week 8 Step 7c: registering offline, and reviewing possible duplicates afterwards."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.patients.models import Patient
from app.modules.patients.service import (
    InvalidPatientError,
    NotWaitingForReviewError,
    PatientNotFoundError,
    PossibleDuplicateError,
    create_patient,
    list_for_review,
    review_patient,
)
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
PHONE = "08031234567"


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
        staff = {
            role: create_staff(
                session,
                tenant_id=tenant.id,
                email=f"{label}-{role}@{run_id}.example.com",
                full_name=f"Test {role}",
                role=role,
                password=PASSWORD,
            )
            for role in ("front_desk", "billing")
        }
        data[label] = {"tenant": tenant, "desk": staff["front_desk"], "billing": staff["billing"]}
    return data


def who(clinic):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic["desk"].id}


def register(session, clinic, *, name="Test Patient Alpha", phone=PHONE, **extra):
    return create_patient(
        session,
        **who(clinic),
        full_name=name,
        date_of_birth=date(1990, 5, 17),
        sex="female",
        phone=phone,
        **extra,
    )


def stored(session, clinic):
    return session.exec(tenant_select(Patient, clinic["tenant"].id)).all()


def actions(session, clinic, prefix):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [event for event in events if event.action.startswith(prefix)]


def test_online_registration_still_asks_the_duplicate_question(session, clinics):
    clinic = clinics["a"]
    register(session, clinic)

    with pytest.raises(PossibleDuplicateError):
        register(session, clinic, name="Someone Else")


def test_offline_registration_of_a_possible_duplicate_is_saved_and_flagged(session, clinics):
    clinic = clinics["a"]
    original = register(session, clinic)

    offline = register(session, clinic, name="Someone Else", registered_offline=True)

    assert offline.id != original.id
    assert offline.review_status == "needs_review"
    assert original.review_status is None
    assert len(stored(session, clinic)) == 2


def test_offline_registration_of_someone_new_needs_no_review(session, clinics):
    offline = register(session, clinics["a"], registered_offline=True)

    assert offline.review_status is None


def test_a_re_sent_registration_creates_nobody_new(session, clinics):
    clinic = clinics["a"]
    device_id = uuid.uuid4()

    first = register(session, clinic, patient_id=device_id, registered_offline=True)
    again = register(session, clinic, patient_id=device_id, registered_offline=True)

    assert first.id == again.id == device_id
    assert len(stored(session, clinic)) == 1
    assert len(actions(session, clinic, "patient.create")) == 1


def test_the_review_list_shows_each_flagged_registration_with_its_matches(session, clinics):
    clinic = clinics["a"]
    original = register(session, clinic)
    offline = register(session, clinic, name="Someone Else", registered_offline=True)

    items = list_for_review(session, **who(clinic))

    assert [item.patient.id for item in items] == [offline.id]
    assert [(match.id, reason) for match, reason in items[0].matches] == [
        (original.id, "same_phone")
    ]
    assert len(actions(session, clinic, "patient.review_list")) == 1


def test_deciding_someone_new_clears_the_flag(session, clinics):
    clinic = clinics["a"]
    register(session, clinic)
    offline = register(session, clinic, name="Someone Else", registered_offline=True)

    decided = review_patient(session, **who(clinic), patient_id=offline.id, duplicate_of=None)

    assert decided.review_status == "confirmed_new"
    assert decided.duplicate_of_id is None
    assert list_for_review(session, **who(clinic)) == []
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    decisions = [event for event in events if event.action == "patient.review"]
    assert [event.patient_id for event in decisions] == [offline.id]


def test_deciding_already_registered_points_at_the_original_and_deletes_nothing(
    session, clinics
):
    clinic = clinics["a"]
    original = register(session, clinic)
    offline = register(session, clinic, name="Someone Else", registered_offline=True)

    decided = review_patient(
        session, **who(clinic), patient_id=offline.id, duplicate_of=original.id
    )

    assert decided.review_status == "duplicate"
    assert decided.duplicate_of_id == original.id
    assert len(stored(session, clinic)) == 2


def test_a_registration_is_decided_only_once(session, clinics):
    clinic = clinics["a"]
    register(session, clinic)
    offline = register(session, clinic, name="Someone Else", registered_offline=True)
    review_patient(session, **who(clinic), patient_id=offline.id, duplicate_of=None)

    with pytest.raises(NotWaitingForReviewError):
        review_patient(session, **who(clinic), patient_id=offline.id, duplicate_of=None)


def test_bad_decisions_are_refused(session, clinics):
    clinic = clinics["a"]
    register(session, clinic)
    offline = register(session, clinic, name="Someone Else", registered_offline=True)
    elsewhere = register(session, clinics["b"])

    with pytest.raises(InvalidPatientError):
        review_patient(session, **who(clinic), patient_id=offline.id, duplicate_of=offline.id)
    with pytest.raises(PatientNotFoundError):  # another clinic's patient
        review_patient(session, **who(clinic), patient_id=offline.id, duplicate_of=elsewhere.id)
    with pytest.raises(PatientNotFoundError):  # another clinic cannot decide
        review_patient(session, **who(clinics["b"]), patient_id=offline.id, duplicate_of=None)


def test_the_review_list_stays_inside_the_clinic(session, clinics):
    register(session, clinics["a"])
    register(session, clinics["a"], name="Someone Else", registered_offline=True)

    assert list_for_review(session, **who(clinics["b"])) == []


# Through the API


def bearer(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_review_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    desk = bearer(session, run_id, "a", "front_desk")
    body = {"full_name": "Test Patient Alpha", "date_of_birth": "1990-05-17", "sex": "female"}
    original = client.post("/api/v1/patients", json={**body, "phone": PHONE}, headers=desk)
    offline = client.post(
        "/api/v1/patients",
        json={**body, "id": str(uuid.uuid4()), "registered_offline": True},
        headers=desk,
    )
    queue = client.get("/api/v1/patients/review-queue", headers=desk)
    billing = client.get(
        "/api/v1/patients/review-queue", headers=bearer(session, run_id, "a", "billing")
    )
    url = f"/api/v1/patients/{offline.json()['id']}/review"
    half = client.post(url, json={"decision": "duplicate"}, headers=desk)
    decided = client.post(
        url,
        json={"decision": "duplicate", "duplicate_of": original.json()["id"]},
        headers=desk,
    )

    assert offline.status_code == 201
    assert offline.json()["review_status"] == "needs_review"
    assert queue.status_code == 200
    assert queue.json()[0]["matches"][0]["patient"]["id"] == original.json()["id"]
    assert queue.json()[0]["matches"][0]["reason"] == "same_name_and_birth_date"
    assert billing.status_code == 403  # billing reads patients but does not register them
    assert half.status_code == 422  # "duplicate" must say of whom
    assert decided.status_code == 200
    assert decided.json()["duplicate_of_id"] == original.json()["id"]
