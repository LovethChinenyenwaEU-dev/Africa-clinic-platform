"""Week 11 Step 6: a patient's record as a FHIR R4 bundle (FR-I1)."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.models import Consent
from app.modules.consent.service import grant_consent, publish_consent_text, revoke_consent
from app.modules.identity.service import create_staff, login
from app.modules.interop import fhir
from app.modules.records.chart import (
    AllergyDetails,
    ProblemDetails,
    record_allergy,
    record_problem,
)
from app.modules.records.models import Allergy, VitalSigns
from app.modules.records.prescriptions import PrescriptionDetails, write_prescription
from app.modules.records.service import open_encounter
from app.modules.records.vitals import VitalReadings, record_vitals
from tests.scheduling_helpers import PASSWORD, build_clinic

STAFF_ROLES = {"desk": "front_desk", "doctor": "doctor", "nurse": "nurse"}


def url(patient_id, reason="patient_request"):
    return f"/api/v1/interop/patients/{patient_id}/fhir?reason={reason}"


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def headers(session, run_id, label, person):
    role = STAFF_ROLES.get(person, person)
    prefix = "" if person in STAFF_ROLES else "fhir-"
    email = f"{prefix}{label}-{role}@{run_id}.example.com"
    token = login(session, email=email, password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def agree(session, clinic, purpose):
    desk = who(clinic, "desk")
    publish_consent_text(session, purpose=purpose, body=f"I agree: {purpose}.", **desk)
    grant_consent(
        session,
        patient_id=clinic["patient"].id,
        purpose=purpose,
        granted_by="patient",
        **who(clinic, "desk"),
    )


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        clinic = build_clinic(session, run_id, label)
        for role in ("admin", "billing"):
            clinic[role] = create_staff(
                session,
                tenant_id=clinic["tenant"].id,
                email=f"fhir-{label}-{role}@{run_id}.example.com",
                full_name=f"Test {role}",
                role=role,
                password=PASSWORD,
            )
        data[label] = clinic
    return data


@pytest.fixture
def record(session, clinics):
    """Clinic A's patient after one visit: vitals, an allergy, a diagnosis, a medicine,
    and consent to treatment."""
    a = clinics["a"]
    encounter = open_encounter(session, **who(a), patient_id=a["patient"].id)
    record_vitals(
        session,
        **who(a, "nurse"),
        encounter_id=encounter.id,
        readings=VitalReadings(
            systolic_mmhg=128, diastolic_mmhg=84, pulse_bpm=88, temperature_c=Decimal("38.4")
        ),
    )
    record_allergy(
        session,
        **who(a),
        encounter_id=encounter.id,
        details=AllergyDetails(substance="Penicillin", reaction="Rash", severity="moderate"),
    )
    record_problem(
        session,
        **who(a),
        encounter_id=encounter.id,
        details=ProblemDetails(
            description="Uncomplicated malaria", category="encounter_diagnosis", code="B54"
        ),
    )
    write_prescription(
        session,
        **who(a),
        encounter_id=encounter.id,
        details=PrescriptionDetails(
            medicine="Artemether-lumefantrine",
            strength="20/120 mg",
            dose="4 tablets",
            frequency="twice daily",
            duration="3 days",
            instructions="Take with food",
        ),
    )
    agree(session, a, "treatment")
    return {"encounter": encounter, **clinics}


def resources(bundle, kind=None):
    found = [entry["resource"] for entry in bundle["entry"]]
    return [r for r in found if kind is None or r["resourceType"] == kind]


def references(value):
    """Every {"reference": ...} anywhere inside a resource."""
    if isinstance(value, dict):
        if "reference" in value:
            yield value["reference"]
        for item in value.values():
            yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


# --- through the API -------------------------------------------------------------------


def test_a_doctor_exports_the_whole_record(session, run_id, record):
    response = TestClient(app).get(
        url(record["a"]["patient"].id), headers=headers(session, run_id, "a", "doctor")
    )

    assert response.status_code == 200
    bundle = response.json()
    assert (bundle["resourceType"], bundle["type"]) == ("Bundle", "collection")
    kinds = sorted(r["resourceType"] for r in resources(bundle))
    assert kinds == sorted(
        [
            "Patient",
            "Organization",
            "Practitioner",  # the doctor
            "Practitioner",  # the nurse who took the vitals
            "Encounter",
            "Observation",  # blood pressure
            "Observation",  # pulse
            "Observation",  # temperature
            "AllergyIntolerance",
            "Condition",
            "MedicationRequest",
            "Consent",
        ]
    )


def test_every_reference_points_inside_the_bundle(session, run_id, record):
    bundle = (
        TestClient(app)
        .get(url(record["a"]["patient"].id), headers=headers(session, run_id, "a", "doctor"))
        .json()
    )

    addresses = {entry["fullUrl"] for entry in bundle["entry"]}
    pointed_at = {ref for resource in resources(bundle) for ref in references(resource)}
    assert pointed_at  # the check below means something
    assert pointed_at <= addresses
    assert len(addresses) == len(bundle["entry"])  # no two resources share an address


def test_the_resources_carry_the_standard_codes(session, run_id, record):
    bundle = (
        TestClient(app)
        .get(url(record["a"]["patient"].id), headers=headers(session, run_id, "a", "doctor"))
        .json()
    )

    patient = resources(bundle, "Patient")[0]
    assert patient["name"] == [{"text": "Test Patient A"}]
    assert (patient["gender"], patient["birthDate"]) == ("female", "1990-05-17")

    by_code = {o["code"]["coding"][0]["code"]: o for o in resources(bundle, "Observation")}
    assert set(by_code) == {"85354-9", "8867-4", "8310-5"}
    pressure = by_code["85354-9"]
    assert [c["valueQuantity"]["value"] for c in pressure["component"]] == [128, 84]
    assert by_code["8310-5"]["valueQuantity"] == {
        "value": 38.4,
        "unit": "Cel",
        "system": "http://unitsofmeasure.org",
        "code": "Cel",
    }

    condition = resources(bundle, "Condition")[0]
    assert condition["code"]["coding"] == [{"system": fhir.ICD_10, "code": "B54"}]
    assert condition["category"][0]["coding"][0]["code"] == "encounter-diagnosis"

    medicine = resources(bundle, "MedicationRequest")[0]
    assert medicine["medicationCodeableConcept"] == {"text": "Artemether-lumefantrine 20/120 mg"}
    assert medicine["status"] == "active"
    assert medicine["dosageInstruction"][0]["text"] == (
        "4 tablets, oral, twice daily, for 3 days. Take with food"
    )

    assert resources(bundle, "Consent")[0]["status"] == "active"
    assert resources(bundle, "Encounter")[0]["status"] == "in-progress"


def test_staff_appear_by_name_only(session, run_id, record):
    bundle = (
        TestClient(app)
        .get(url(record["a"]["patient"].id), headers=headers(session, run_id, "a", "doctor"))
        .json()
    )

    for person in resources(bundle, "Practitioner"):
        assert set(person) == {"resourceType", "id", "name"}
    assert "example.com" not in str(bundle)  # no staff email


def test_a_nurse_may_export_too(session, run_id, record):
    response = TestClient(app).get(
        url(record["a"]["patient"].id), headers=headers(session, run_id, "a", "nurse")
    )

    assert response.status_code == 200


@pytest.mark.parametrize("person", ["desk", "admin", "billing"])
def test_others_cannot_export(session, run_id, record, person):
    response = TestClient(app).get(
        url(record["a"]["patient"].id), headers=headers(session, run_id, "a", person)
    )

    assert response.status_code == 403


def test_another_clinics_patient_is_not_found(session, run_id, record):
    doctor_b = headers(session, run_id, "b", "doctor")

    other = TestClient(app).get(url(record["a"]["patient"].id), headers=doctor_b)
    unknown = TestClient(app).get(url(uuid.uuid4()), headers=doctor_b)

    assert other.status_code == 404
    assert unknown.status_code == 404


@pytest.mark.parametrize("reason", ["referral", "transfer"])
def test_sending_it_elsewhere_needs_sharing_consent(session, run_id, record, reason):
    a = record["a"]
    doctor = headers(session, run_id, "a", "doctor")

    refused = TestClient(app).get(url(a["patient"].id, reason), headers=doctor)
    agree(session, a, "referral_sharing")
    allowed = TestClient(app).get(url(a["patient"].id, reason), headers=doctor)

    assert refused.status_code == 409
    assert "consent" in refused.json()["detail"]
    assert allowed.status_code == 200


def test_every_export_is_in_the_audit_log_with_its_reason(session, run_id, record):
    a = record["a"]
    doctor = headers(session, run_id, "a", "doctor")

    TestClient(app).get(url(a["patient"].id, "referral"), headers=doctor)  # refused
    TestClient(app).get(url(a["patient"].id), headers=doctor)

    exports = [
        e
        for e in list_audit_events(session, tenant_id=a["tenant"].id)
        if e.action == "record.export"
    ]
    assert [(e.actor_id, e.patient_id, e.purpose) for e in exports] == [
        (a["doctor"].id, a["patient"].id, "patient_request")
    ]


def test_an_unknown_reason_is_refused(session, run_id, record):
    response = TestClient(app).get(
        url(record["a"]["patient"].id, "curiosity"),
        headers=headers(session, run_id, "a", "doctor"),
    )

    assert response.status_code == 422


def test_a_revoked_consent_is_exported_as_inactive(session, run_id, record):
    a = record["a"]
    revoke_consent(session, **who(a, "desk"), patient_id=a["patient"].id, purpose="treatment")

    bundle = (
        TestClient(app)
        .get(url(a["patient"].id), headers=headers(session, run_id, "a", "doctor"))
        .json()
    )

    consent = resources(bundle, "Consent")[0]
    assert consent["status"] == "inactive"
    assert "end" in consent["provision"]["period"]


# --- the mappings, without a database --------------------------------------------------

WHEN = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
IDS = {name: uuid.uuid4() for name in ("set", "patient", "encounter", "staff")}


def test_only_readings_taken_become_observations():
    row = VitalSigns(
        id=IDS["set"],
        patient_id=IDS["patient"],
        encounter_id=IDS["encounter"],
        recorded_by_id=IDS["staff"],
        status="current",
        systolic_mmhg=120,  # no diastolic: no blood pressure
        spo2_pct=97,
        measured_at=WHEN,
    )

    found = fhir.vital_observations(row)

    assert [o["code"]["coding"][0]["code"] for o in found] == ["59408-5"]
    assert found[0]["status"] == "final"


def test_a_correction_is_amended_and_ids_stay_the_same_on_a_second_export():
    row = VitalSigns(
        id=IDS["set"],
        patient_id=IDS["patient"],
        encounter_id=IDS["encounter"],
        recorded_by_id=IDS["staff"],
        status="current",
        replaces_id=uuid.uuid4(),
        pulse_bpm=70,
        measured_at=WHEN,
    )

    first, second = fhir.vital_observations(row), fhir.vital_observations(row)

    assert first[0]["status"] == "amended"
    assert first[0]["id"] == second[0]["id"]


def test_an_allergy_made_in_error_is_marked_not_hidden():
    row = Allergy(
        id=uuid.uuid4(),
        patient_id=IDS["patient"],
        encounter_id=IDS["encounter"],
        recorded_by_id=IDS["staff"],
        substance="Sulfa",
        severity="unknown",
        clinical_status="entered_in_error",
        version_status="current",
        recorded_at=WHEN,
    )

    resource = fhir.allergy(row)

    assert resource["verificationStatus"]["coding"][0]["code"] == "entered-in-error"
    assert "clinicalStatus" not in resource  # FHIR forbids it on an entry made in error
    assert "reaction" not in resource  # nothing recorded: nothing invented


def test_a_caregivers_consent_says_so():
    row = Consent(
        id=uuid.uuid4(),
        patient_id=IDS["patient"],
        purpose="treatment",
        consent_text_id=uuid.uuid4(),
        granted_by="caregiver",
        granted_at=WHEN,
    )

    resource = fhir.consent(row, organization_id=uuid.uuid4(), wording_version=2)

    assert resource["performer"] == [{"display": "Caregiver, on the patient's behalf"}]
    assert resource["policyRule"] == {"text": "Clinic consent wording, version 2"}
    assert resource["provision"]["purpose"][0]["code"] == "treatment"


def test_the_bundle_wraps_each_resource_under_its_own_address():
    made = fhir.bundle(
        [{"resourceType": "Patient", "id": "p1"}], bundle_id=uuid.uuid4(), made_at=WHEN
    )

    assert made["entry"] == [
        {"fullUrl": "urn:uuid:p1", "resource": {"resourceType": "Patient", "id": "p1"}}
    ]
    assert made["timestamp"] == "2026-11-02T09:30:00+00:00"
