"""Week 11: merging a duplicate patient into the original. Everything moves; nothing is
deleted; the audit log is untouched apart from the merge lines."""
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.models import Consent
from app.modules.consent.service import (
    grant_consent,
    has_active_consent,
    publish_consent_text,
    revoke_consent,
)
from app.modules.identity.service import create_staff, login
from app.modules.patients.merge import tables_with_patients
from app.modules.patients.models import Patient
from app.modules.patients.service import create_patient, find_possible_duplicates, review_patient
from app.modules.portal.models import PatientLoginCode
from app.modules.records.chart import AllergyDetails, record_allergy
from app.modules.records.models import Allergy, Encounter
from app.modules.records.service import open_encounter
from app.modules.scheduling.models import Appointment
from tests.scheduling_helpers import PASSWORD, book, build_clinic

STAFF_ROLES = {"desk": "front_desk", "doctor": "doctor", "nurse": "nurse"}


def headers(session, run_id, label, person):
    if person in STAFF_ROLES:
        email = f"{label}-{STAFF_ROLES[person]}@{run_id}.example.com"
    else:
        email = f"merge-{label}-{person}@{run_id}.example.com"
    return {"Authorization": f"Bearer {login(session, email=email, password=PASSWORD)}"}


def url(patient):
    return f"/api/v1/patients/{patient.id}/merge"


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def offline_twin(session, clinic):
    """The same person registered again offline: saved, flagged for review."""
    original = clinic["patient"]
    return create_patient(
        session,
        **who(clinic),
        full_name=original.full_name,
        date_of_birth=original.date_of_birth,
        sex=original.sex,
        registered_offline=True,
    )


def found_duplicate(session, clinic):
    twin = offline_twin(session, clinic)
    return review_patient(
        session, **who(clinic), patient_id=twin.id, duplicate_of=clinic["patient"].id
    )


def agree(session, clinic, patient):
    grant_consent(
        session, **who(clinic), patient_id=patient.id, purpose="treatment", granted_by="patient"
    )


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        clinic = build_clinic(session, run_id, label)
        clinic["billing"] = create_staff(
            session,
            tenant_id=clinic["tenant"].id,
            email=f"merge-{label}-billing@{run_id}.example.com",
            full_name="Test billing",
            role="billing",
            password=PASSWORD,
        )
        publish_consent_text(
            session, **who(clinic), purpose="treatment", body="I agree to be treated."
        )
        data[label] = clinic
    return data


@pytest.fixture
def twin(session, clinics):
    """Clinic A: the duplicate had a visit, an encounter with an allergy, a consent and a
    pending SMS sign-in code while it was in use."""
    a = clinics["a"]
    duplicate = found_duplicate(session, a)
    agree(session, a, duplicate)
    agree(session, a, a["patient"])
    book(session, a, patient_id=duplicate.id)
    encounter = open_encounter(session, **who(a, "doctor"), patient_id=duplicate.id)
    record_allergy(
        session,
        **who(a, "doctor"),
        encounter_id=encounter.id,
        details=AllergyDetails(substance="Penicillin"),
    )
    now = datetime.now(UTC)
    session.add(
        PatientLoginCode(
            tenant_id=a["tenant"].id,
            patient_id=duplicate.id,
            phone="+2348030000000",
            code_hash="x",
            expires_at=now + timedelta(minutes=10),
        )
    )
    session.commit()
    return duplicate


def owned_by(session, clinic, model, patient):
    statement = tenant_select(model, clinic["tenant"].id).where(model.patient_id == patient.id)
    return session.exec(statement).all()


def test_everything_moves_to_the_original(session, run_id, clinics, twin):
    a = clinics["a"]

    response = TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    assert response.status_code == 200
    body = response.json()
    assert body["original"]["id"] == str(a["patient"].id)
    assert body["duplicate"]["review_status"] == "merged"
    assert body["moved"] == {"appointment": 1, "encounter": 1, "allergy": 1, "consent": 1}
    session.expire_all()
    for model in (Appointment, Encounter, Allergy, Consent):
        assert owned_by(session, a, model, twin) == []
    assert len(owned_by(session, a, Consent, a["patient"])) == 2


def test_the_duplicate_record_is_kept(session, run_id, clinics, twin):
    TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    session.expire_all()
    kept = session.get(Patient, twin.id)
    assert kept is not None
    assert (kept.review_status, kept.duplicate_of_id) == ("merged", clinics["a"]["patient"].id)


def test_the_merge_is_written_on_both_records_and_old_lines_stay(
    session, run_id, clinics, twin
):
    a = clinics["a"]
    before = list_audit_events(session, tenant_id=a["tenant"].id, limit=200)
    old_lines_on_twin = {e.id for e in before if e.patient_id == twin.id}

    TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    after = list_audit_events(session, tenant_id=a["tenant"].id, limit=200)
    merges = {(e.patient_id, e.entity_id) for e in after if e.action == "patient.merge"}
    assert merges == {(a["patient"].id, twin.id), (twin.id, a["patient"].id)}
    still_on_twin = {e.id for e in after if e.patient_id == twin.id}
    assert old_lines_on_twin <= still_on_twin  # history is not rewritten


def test_unused_sign_in_codes_for_the_duplicate_are_thrown_away(session, run_id, clinics, twin):
    TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    session.expire_all()
    codes = session.exec(
        tenant_select(PatientLoginCode, clinics["a"]["tenant"].id).where(
            PatientLoginCode.patient_id == twin.id
        )
    ).all()
    assert codes == []


def test_withdrawing_consent_after_a_merge_ends_both(session, run_id, clinics, twin):
    a = clinics["a"]
    TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    revoke_consent(session, **who(a), patient_id=a["patient"].id, purpose="treatment")

    assert not has_active_consent(
        session, tenant_id=a["tenant"].id, patient_id=a["patient"].id, purpose="treatment"
    )


def test_a_merged_record_is_no_longer_offered_as_a_possible_duplicate(
    session, run_id, clinics, twin
):
    a = clinics["a"]
    TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    session.expire_all()
    found = find_possible_duplicates(
        session,
        tenant_id=a["tenant"].id,
        full_name=a["patient"].full_name,
        date_of_birth=a["patient"].date_of_birth,
        phone=None,
    )
    assert [match.patient_id for match in found] == [a["patient"].id]


def test_merging_twice_is_refused(session, run_id, twin):
    desk = headers(session, run_id, "a", "desk")

    TestClient(app).post(url(twin), headers=desk)
    again = TestClient(app).post(url(twin), headers=desk)

    assert again.status_code == 409


def test_only_a_record_found_to_be_a_duplicate_can_be_merged(session, run_id, clinics):
    a = clinics["a"]
    waiting = offline_twin(session, a)  # not reviewed yet
    desk = headers(session, run_id, "a", "desk")

    not_reviewed = TestClient(app).post(url(waiting), headers=desk)
    ordinary = TestClient(app).post(url(a["patient"]), headers=desk)

    assert not_reviewed.status_code == 409
    assert ordinary.status_code == 409


def test_the_original_must_not_itself_be_a_duplicate(session, run_id, clinics, twin):
    a = clinics["a"]
    third = create_patient(
        session,
        **who(a),
        full_name="Someone Else",
        date_of_birth=date(1970, 1, 1),
        sex="male",
    )
    original = session.get(Patient, a["patient"].id)
    original.review_status, original.duplicate_of_id = "duplicate", third.id
    session.add(original)
    session.commit()

    response = TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "desk"))

    assert response.status_code == 409
    assert "itself a duplicate" in response.json()["detail"]


def test_another_clinic_gets_not_found(session, run_id, twin):
    other = TestClient(app).post(url(twin), headers=headers(session, run_id, "b", "desk"))
    unknown = TestClient(app).post(
        f"/api/v1/patients/{uuid.uuid4()}/merge", headers=headers(session, run_id, "b", "desk")
    )

    assert other.status_code == 404
    assert unknown.status_code == 404


def test_billing_cannot_merge(session, run_id, twin):
    response = TestClient(app).post(url(twin), headers=headers(session, run_id, "a", "billing"))

    assert response.status_code == 403


def test_every_patient_table_is_moved_and_the_audit_log_never_is():
    names = {table.name for table in tables_with_patients()}

    assert {"appointment", "encounter", "consent", "invoice", "prescription"} <= names
    assert "audit_event" not in names
    assert "patient_login_code" not in names
