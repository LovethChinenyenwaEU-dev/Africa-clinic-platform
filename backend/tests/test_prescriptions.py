"""Week 9 Step 1: prescriptions (FR-R2). Doctors write and change them; versions kept."""
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.records.models import Prescription
from app.modules.records.prescriptions import (
    InvalidPrescriptionError,
    NotAPrescriberError,
    PrescriptionDetails,
    PrescriptionNotFoundError,
    list_encounter_prescriptions,
    resolve_prescription_conflict,
    revise_prescription,
    write_prescription,
)
from app.modules.records.service import (
    EncounterNotOpenError,
    close_encounter,
    mark_entered_in_error,
    open_encounter,
)
from tests.scheduling_helpers import PASSWORD, build_clinic

ACT = PrescriptionDetails(
    medicine="  Artemether-lumefantrine ",
    strength="20/120 mg",
    dose="4 tablets",
    frequency="twice daily",
    duration="3 days",
    instructions="Take with food",
)

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "encounter_id",
    "patient_id",
    "version_status",
    "replaces_id",
    "medicine",
    "strength",
    "dose",
    "route",
    "frequency",
    "duration",
    "instructions",
    "clinical_status",
    "recorded_by_id",
    "recorded_at",
    "written_at",
    "synced_late",
}


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def visit(session, clinic, **extra):
    return open_encounter(
        session, **who(clinic), patient_id=clinic["patient"].id, **extra
    )


def prescribe(session, clinic, encounter, person="doctor", details=ACT, **extra):
    return write_prescription(
        session, **who(clinic, person), encounter_id=encounter.id, details=details, **extra
    )


def stored(session, clinic):
    return session.exec(tenant_select(Prescription, clinic["tenant"].id)).all()


def actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(e.action for e in events if e.action.startswith("prescription."))


def test_prescription_table_columns_are_exactly_these():
    assert set(Prescription.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_a_doctor_prescribes_in_an_open_encounter(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    written = prescribe(session, clinic, encounter)

    assert written.medicine == "Artemether-lumefantrine"  # tidied
    assert written.route == "oral"
    assert written.clinical_status == "active"
    assert written.version_status == "current"
    assert written.patient_id == clinic["patient"].id
    assert written.synced_late is False
    assert actions(session, clinic) == ["prescription.write"]


@pytest.mark.parametrize("person", ["nurse", "desk"])
def test_only_doctors_prescribe(session, clinics, person):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(NotAPrescriberError):
        prescribe(session, clinic, encounter, person=person)
    assert stored(session, clinic) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"medicine": "   "},
        {"dose": ""},
        {"frequency": ""},
        {"duration": ""},
        {"route": "by mouth"},
        {"medicine": "x" * 201},
        {"instructions": "x" * 501},
        {"clinical_status": "stopped"},  # a new prescription starts active
    ],
)
def test_incomplete_or_wrong_prescriptions_are_refused(session, clinics, changes):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(InvalidPrescriptionError):
        prescribe(session, clinic, encounter, details=replace(ACT, **changes))
    assert stored(session, clinic) == []


def test_a_re_sent_prescription_is_saved_once(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    device_id = uuid.uuid4()

    first = prescribe(session, clinic, encounter, prescription_id=device_id)
    again = prescribe(session, clinic, encounter, prescription_id=device_id)

    assert first.id == again.id == device_id
    assert len(stored(session, clinic)) == 1


def test_written_offline_before_sign_off_is_accepted_and_marked_late(session, clinics):
    clinic = clinics["a"]
    now = datetime.now(UTC)
    encounter = visit(session, clinic, now=now - timedelta(hours=2))
    close_encounter(session, **who(clinic), encounter_id=encounter.id, now=now - timedelta(hours=1))

    with pytest.raises(EncounterNotOpenError):  # no device time: written after sign-off
        prescribe(session, clinic, encounter)
    late = prescribe(session, clinic, encounter, written_at=now - timedelta(minutes=90))

    assert late.synced_late is True


def test_stopping_is_a_new_version_and_allowed_after_sign_off(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = prescribe(session, clinic, encounter)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    stopped = revise_prescription(
        session,
        **who(clinic),
        prescription_id=original.id,
        details=replace(ACT, clinical_status="stopped"),
    )

    session.refresh(original)
    assert original.version_status == "superseded"
    assert original.clinical_status == "active"  # the old version is never changed
    assert stopped.version_status == "current"
    assert stopped.clinical_status == "stopped"
    assert stopped.replaces_id == original.id
    assert actions(session, clinic) == ["prescription.revise", "prescription.write"]


def test_one_entered_in_error_is_hidden_but_kept_in_history(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = prescribe(session, clinic, encounter)
    revise_prescription(
        session,
        **who(clinic),
        prescription_id=original.id,
        details=replace(ACT, clinical_status="entered_in_error"),
    )

    shown = list_encounter_prescriptions(session, **who(clinic, "nurse"), encounter_id=encounter.id)
    history = list_encounter_prescriptions(
        session, **who(clinic, "nurse"), encounter_id=encounter.id, include_history=True
    )

    assert shown == []
    assert len(history) == 2
    assert "prescription.view" in actions(session, clinic)


def test_no_changes_in_an_encounter_marked_as_a_mistake(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = prescribe(session, clinic, encounter)
    mark_entered_in_error(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        revise_prescription(session, **who(clinic), prescription_id=original.id, details=ACT)


def test_two_devices_changing_one_prescription_keep_both_until_a_doctor_chooses(
    session, clinics
):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = prescribe(session, clinic, encounter)
    first = revise_prescription(
        session, **who(clinic), prescription_id=original.id, details=replace(ACT, duration="5 days")
    )
    second = revise_prescription(
        session,
        **who(clinic),
        prescription_id=original.id,
        details=replace(ACT, clinical_status="stopped"),
    )

    assert second.version_status == "conflict"
    shown = list_encounter_prescriptions(session, **who(clinic), encounter_id=encounter.id)
    assert {row.id for row in shown} == {first.id, second.id}

    kept = resolve_prescription_conflict(
        session, **who(clinic), conflict_id=second.id, keep_conflict=True
    )

    session.refresh(first)
    assert kept.id == second.id and kept.version_status == "current"
    assert first.version_status == "superseded"
    with pytest.raises(NotAPrescriberError):
        resolve_prescription_conflict(
            session, **who(clinic, "nurse"), conflict_id=second.id, keep_conflict=True
        )


def test_another_clinic_cannot_change_a_prescription(session, clinics):
    encounter = visit(session, clinics["a"])
    original = prescribe(session, clinics["a"], encounter)

    with pytest.raises(PrescriptionNotFoundError):
        revise_prescription(session, **who(clinics["b"]), prescription_id=original.id, details=ACT)


def test_prescribing_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    encounter = visit(session, clinics["a"])
    url = f"/api/v1/encounters/{encounter.id}/prescriptions"

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    body = {"medicine": "Paracetamol", "dose": "1 g", "frequency": "8-hourly", "duration": "3 days"}
    by_doctor = client.post(url, json=body, headers=bearer("doctor"))
    by_nurse = client.post(url, json=body, headers=bearer("nurse"))
    nurse_reads = client.get(url, headers=bearer("nurse"))

    assert by_doctor.status_code == 201
    assert by_doctor.json()["route"] == "oral"
    assert by_nurse.status_code == 403
    assert nurse_reads.status_code == 200
    assert [row["medicine"] for row in nurse_reads.json()] == ["Paracetamol"]
