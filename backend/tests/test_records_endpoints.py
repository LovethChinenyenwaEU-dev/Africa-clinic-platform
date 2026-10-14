import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.records.models import ClinicalNote, Encounter, VitalSigns
from tests.scheduling_helpers import PASSWORD, build_clinic

API = "/api/v1"
CLINICAL_PREFIXES = ("encounter.", "vitals.", "allergy.", "problem.", "note.")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinics(session, run_id):
    """Clinic A also has an admin and a billing clerk. Clinic B has its own people."""
    data = {label: build_clinic(session, run_id, label) for label in ("a", "b")}
    for role in ("admin", "billing"):
        create_staff(
            session,
            tenant_id=data["a"]["tenant"].id,
            email=f"a-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
    return data


def headers(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def stored(session, clinic, model):
    return session.exec(tenant_select(model, clinic["tenant"].id)).all()


def clinical_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith(CLINICAL_PREFIXES))


def open_visit(client, clinic, h):
    response = client.post(
        f"{API}/encounters", json={"patient_id": str(clinic["patient"].id)}, headers=h
    )
    assert response.status_code == 201
    return response.json()


def test_a_doctor_records_a_whole_visit_through_the_api(client, session, run_id, clinics):
    a = clinics["a"]
    doctor = headers(session, run_id, "a", "doctor")
    nurse = headers(session, run_id, "a", "nurse")
    patient = str(a["patient"].id)

    encounter = open_visit(client, a, doctor)
    eid = encounter["id"]
    vitals = client.post(
        f"{API}/encounters/{eid}/vitals",
        json={"temperature_c": "38.4", "pulse_bpm": 104},
        headers=nurse,
    )
    allergy = client.post(
        f"{API}/encounters/{eid}/allergies",
        json={"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"},
        headers=doctor,
    )
    problem = client.post(
        f"{API}/encounters/{eid}/problems",
        json={
            "description": "Uncomplicated malaria",
            "category": "encounter_diagnosis",
            "code": "b54",
        },
        headers=doctor,
    )
    note = client.post(
        f"{API}/encounters/{eid}/notes",
        json={"kind": "assessment", "body": "Likely malaria.\nStart treatment."},
        headers=doctor,
    )
    closed = client.post(f"{API}/encounters/{eid}/close", headers=doctor)

    assert [r.status_code for r in (vitals, allergy, problem, note)] == [201] * 4
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert vitals.json()["temperature_c"] == "38.4"  # exact, no float rounding
    assert vitals.json()["recorded_by_id"] == str(a["nurse"].id)
    assert problem.json()["code"] == "B54"
    assert note.json()["body"] == "Likely malaria.\nStart treatment."
    for response in (encounter, vitals.json(), allergy.json(), problem.json(), note.json()):
        assert "tenant_id" not in response

    reads = [
        client.get(f"{API}/encounters/{eid}", headers=nurse),
        client.get(f"{API}/encounters/{eid}/vitals", headers=nurse),
        client.get(f"{API}/encounters/{eid}/notes", headers=nurse),
        client.get(f"{API}/patients/{patient}/allergies", headers=nurse),
        client.get(f"{API}/patients/{patient}/problems", headers=nurse),
        client.get(f"{API}/patients/{patient}/encounters", headers=nurse),
    ]
    assert [r.status_code for r in reads] == [200] * 6
    assert [item["substance"] for item in reads[3].json()] == ["Penicillin"]
    assert clinical_actions(session, a) == sorted(
        [
            "encounter.create",
            "vitals.record",
            "allergy.record",
            "problem.record",
            "note.write",
            "encounter.close",
            "encounter.view",
            "vitals.view",
            "note.view",
            "allergy.view",
            "problem.view",
            "encounter.list",
        ]
    )


@pytest.mark.parametrize("role", ["front_desk", "admin", "billing"])
def test_nobody_but_doctors_and_nurses_can_touch_the_record(
    client, session, run_id, clinics, role
):
    a = clinics["a"]
    encounter = open_visit(client, a, headers(session, run_id, "a", "doctor"))
    eid, patient = encounter["id"], str(a["patient"].id)
    h = headers(session, run_id, "a", role)

    attempts = [
        client.post(f"{API}/encounters", json={"patient_id": patient}, headers=h),
        client.get(f"{API}/encounters/{eid}", headers=h),
        client.post(f"{API}/encounters/{eid}/vitals", json={"pulse_bpm": 80}, headers=h),
        client.get(f"{API}/encounters/{eid}/vitals", headers=h),
        client.post(f"{API}/encounters/{eid}/notes", json={"kind": "plan", "body": "x"}, headers=h),
        client.get(f"{API}/encounters/{eid}/notes", headers=h),
        client.get(f"{API}/patients/{patient}/allergies", headers=h),
        client.get(f"{API}/patients/{patient}/problems", headers=h),
        client.get(f"{API}/patients/{patient}/encounters", headers=h),
        client.post(f"{API}/encounters/{eid}/close", headers=h),
    ]

    assert [attempt.status_code for attempt in attempts] == [403] * len(attempts)
    assert len(stored(session, a, Encounter)) == 1
    assert stored(session, a, VitalSigns) == []
    assert clinical_actions(session, a) == ["encounter.create"]


def test_another_clinic_gets_not_found_and_nothing_is_written(client, session, run_id, clinics):
    a = clinics["a"]
    encounter = open_visit(client, a, headers(session, run_id, "a", "doctor"))
    eid, patient = encounter["id"], str(a["patient"].id)
    h = headers(session, run_id, "b", "doctor")

    attempts = [
        client.get(f"{API}/encounters/{eid}", headers=h),
        client.post(f"{API}/encounters/{eid}/vitals", json={"pulse_bpm": 80}, headers=h),
        client.get(f"{API}/encounters/{eid}/notes", headers=h),
        client.get(f"{API}/patients/{patient}/allergies", headers=h),
        client.post(f"{API}/encounters", json={"patient_id": patient}, headers=h),
    ]

    assert [attempt.status_code for attempt in attempts] == [404] * len(attempts)
    assert {attempt.json()["detail"] for attempt in attempts} == {"Not found."}
    assert stored(session, clinics["b"], Encounter) == []
    assert clinical_actions(session, clinics["b"]) == []


def test_a_nurse_cannot_close_the_doctors_encounter(client, session, run_id, clinics):
    a = clinics["a"]
    encounter = open_visit(client, a, headers(session, run_id, "a", "doctor"))

    response = client.post(
        f"{API}/encounters/{encounter['id']}/close", headers=headers(session, run_id, "a", "nurse")
    )

    assert response.status_code == 403
    (still_open,) = stored(session, a, Encounter)
    assert still_open.status == "open"


def test_a_mistyped_vital_gets_422_and_nothing_is_saved(client, session, run_id, clinics):
    a = clinics["a"]
    h = headers(session, run_id, "a", "doctor")
    encounter = open_visit(client, a, h)

    response = client.post(
        f"{API}/encounters/{encounter['id']}/vitals", json={"temperature_c": "370"}, headers=h
    )

    assert response.status_code == 422
    assert stored(session, a, VitalSigns) == []


def test_a_retried_request_with_the_same_id_creates_nothing_new(client, session, run_id, clinics):
    a = clinics["a"]
    h = headers(session, run_id, "a", "doctor")
    form = {"id": str(uuid.uuid4()), "patient_id": str(a["patient"].id)}

    first = client.post(f"{API}/encounters", json=form, headers=h)
    again = client.post(f"{API}/encounters", json=form, headers=h)

    assert first.json()["id"] == again.json()["id"] == form["id"]
    assert len(stored(session, a, Encounter)) == 1


def test_only_the_author_can_amend_a_note(client, session, run_id, clinics):
    a = clinics["a"]
    doctor = headers(session, run_id, "a", "doctor")
    encounter = open_visit(client, a, doctor)
    note = client.post(
        f"{API}/encounters/{encounter['id']}/notes",
        json={"kind": "history", "body": "Fever for 3 days."},
        headers=doctor,
    ).json()

    by_nurse = client.post(
        f"{API}/notes/{note['id']}/amendments",
        json={"body": "Fever for 5 days."},
        headers=headers(session, run_id, "a", "nurse"),
    )
    by_author = client.post(
        f"{API}/notes/{note['id']}/amendments", json={"body": "Fever for 4 days."}, headers=doctor
    )

    assert by_nurse.status_code == 403
    assert by_author.status_code == 201
    assert by_author.json()["replaces_id"] == note["id"]
    assert len(stored(session, a, ClinicalNote)) == 2
