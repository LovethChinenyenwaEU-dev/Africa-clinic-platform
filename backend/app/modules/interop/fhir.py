"""Our records as HL7 FHIR R4 resources (Week 11 Step 6, FR-I1). Plain dictionaries.

Each function turns one of our rows into one FHIR resource. References inside the
export use "urn:uuid:<our id>", so the bundle stands alone: another system can read it
without calling us. Codes follow FHIR's own value sets; where we only have words (a
medicine, an allergy), they go in `text`, which FHIR allows.

Mappings worth knowing:
- vital signs: one set of ours becomes one Observation per reading, with the LOINC code
  FHIR's vital-signs profile asks for; blood pressure is one Observation with two parts;
- a correction (it replaces an earlier set) is "amended"; the earlier one is not exported;
- "entered_in_error" becomes FHIR's "entered-in-error" everywhere;
- a revoked consent is "inactive", with the time it ended.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.modules.consent.models import Consent
from app.modules.identity.models import Staff
from app.modules.patients.models import Patient
from app.modules.records.models import Allergy, Encounter, Prescription, Problem, VitalSigns
from app.modules.tenancy.models import Tenant

Resource = dict[str, Any]

LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
ICD_10 = "http://hl7.org/fhir/sid/icd-10"
TERMINOLOGY = "http://terminology.hl7.org/CodeSystem"
# Our own code list for consent purposes, and our patient numbers.
CONSENT_PURPOSE_SYSTEM = "urn:afripeak:consent-purpose"
PATIENT_ID_SYSTEM = "urn:afripeak:patient-id"

ROUTE_TEXT = {
    "oral": "Oral",
    "iv": "Intravenous",
    "im": "Intramuscular",
    "sc": "Subcutaneous",
    "topical": "Topical",
    "inhaled": "Inhaled",
    "rectal": "Rectal",
    "vaginal": "Vaginal",
    "eye": "Eye",
    "ear": "Ear",
    "nasal": "Nasal",
    "other": "Other",
}

# (field, LOINC code, display, UCUM unit) for each single reading in a vital-signs set.
SINGLE_READINGS = (
    ("pulse_bpm", "8867-4", "Heart rate", "/min"),
    ("respiratory_rate", "9279-1", "Respiratory rate", "/min"),
    ("spo2_pct", "59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry", "%"),
    ("temperature_c", "8310-5", "Body temperature", "Cel"),
    ("weight_kg", "29463-7", "Body weight", "kg"),
    ("height_cm", "8302-2", "Body height", "cm"),
)


def ref(row_id: uuid.UUID) -> dict[str, str]:
    return {"reference": f"urn:uuid:{row_id}"}


def _instant(moment: datetime) -> str:
    return moment.isoformat()


def _day(day: date) -> str:
    return day.isoformat()


def _code(system: str, code: str, display: str | None = None) -> dict[str, Any]:
    coding: dict[str, Any] = {"system": system, "code": code}
    if display:
        coding["display"] = display
    return {"coding": [coding]}


def _fhir_status(value: str) -> str:
    """Our statuses use underscores; FHIR's use hyphens."""
    return value.replace("_", "-")


def _number(value: int | Decimal) -> int | float:
    return float(value) if isinstance(value, Decimal) else value


def organization(tenant: Tenant) -> Resource:
    return {"resourceType": "Organization", "id": str(tenant.id), "name": tenant.name}


def practitioner(staff: Staff) -> Resource:
    """Who recorded or prescribed. A name only: no email, no account details."""
    return {
        "resourceType": "Practitioner",
        "id": str(staff.id),
        "name": [{"text": staff.full_name}],
    }


def patient(row: Patient, tenant: Tenant) -> Resource:
    resource: Resource = {
        "resourceType": "Patient",
        "id": str(row.id),
        "identifier": [{"system": PATIENT_ID_SYSTEM, "value": str(row.id)}],
        "name": [{"text": row.full_name}],
        "gender": row.sex if row.sex in ("female", "male", "other") else "unknown",
        "birthDate": _day(row.date_of_birth),
        "managingOrganization": ref(tenant.id),
    }
    if row.phone:
        resource["telecom"] = [{"system": "phone", "value": row.phone, "use": "mobile"}]
    return resource


ENCOUNTER_STATUS = {"open": "in-progress", "closed": "finished"}


def encounter(row: Encounter, *, remote: bool) -> Resource:
    period: dict[str, str] = {"start": _instant(row.opened_at)}
    if row.closed_at:
        period["end"] = _instant(row.closed_at)
    return {
        "resourceType": "Encounter",
        "id": str(row.id),
        "status": ENCOUNTER_STATUS.get(row.status, _fhir_status(row.status)),
        "class": (
            {"system": f"{TERMINOLOGY}/v3-ActCode", "code": "VR", "display": "virtual"}
            if remote
            else {"system": f"{TERMINOLOGY}/v3-ActCode", "code": "AMB", "display": "ambulatory"}
        ),
        "subject": ref(row.patient_id),
        "participant": [{"individual": ref(row.clinician_id)}],
        "period": period,
    }


def _vital_base(row: VitalSigns, part: str, code: str, display: str) -> Resource:
    return {
        "resourceType": "Observation",
        # One id per reading, made from the set's id so a second export gives the same ids.
        "id": str(uuid.uuid5(row.id, part)),
        "status": "amended" if row.replaces_id else "final",
        "category": [
            {
                "coding": [
                    {
                        "system": f"{TERMINOLOGY}/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs",
                    }
                ]
            }
        ],
        "code": _code(LOINC, code, display),
        "subject": ref(row.patient_id),
        "encounter": ref(row.encounter_id),
        "effectiveDateTime": _instant(row.measured_at),
        "performer": [ref(row.recorded_by_id)],
    }


def _quantity(value: int | Decimal, unit: str) -> dict[str, Any]:
    return {"value": _number(value), "unit": unit, "system": UCUM, "code": unit}


def vital_observations(row: VitalSigns) -> list[Resource]:
    """One Observation per reading taken. Readings left empty are not invented."""
    found: list[Resource] = []
    if row.systolic_mmhg is not None and row.diastolic_mmhg is not None:
        pressure = _vital_base(row, "blood_pressure", "85354-9", "Blood pressure panel")
        pressure["component"] = [
            {
                "code": _code(LOINC, "8480-6", "Systolic blood pressure"),
                "valueQuantity": _quantity(row.systolic_mmhg, "mm[Hg]"),
            },
            {
                "code": _code(LOINC, "8462-4", "Diastolic blood pressure"),
                "valueQuantity": _quantity(row.diastolic_mmhg, "mm[Hg]"),
            },
        ]
        found.append(pressure)
    for field, code, display, unit in SINGLE_READINGS:
        value = getattr(row, field)
        if value is not None:
            reading = _vital_base(row, field, code, display)
            reading["valueQuantity"] = _quantity(value, unit)
            found.append(reading)
    return found


def _clinical_status(kind: str, value: str) -> dict[str, Any]:
    return _code(f"{TERMINOLOGY}/{kind}", value)


def _verification(kind: str, entered_in_error: bool) -> dict[str, Any]:
    return _code(f"{TERMINOLOGY}/{kind}", "entered-in-error" if entered_in_error else "confirmed")


def allergy(row: Allergy) -> Resource:
    wrong = row.clinical_status == "entered_in_error"
    resource: Resource = {
        "resourceType": "AllergyIntolerance",
        "id": str(row.id),
        "verificationStatus": _verification("allergyintolerance-verification", wrong),
        "code": {"text": row.substance},
        "patient": ref(row.patient_id),
        "encounter": ref(row.encounter_id),
        "recordedDate": _instant(row.recorded_at),
        "recorder": ref(row.recorded_by_id),
    }
    if not wrong:  # FHIR: no clinical status on an entry made in error
        resource["clinicalStatus"] = _clinical_status(
            "allergyintolerance-clinical", row.clinical_status
        )
    if row.reaction or row.severity in ("mild", "moderate", "severe"):
        reaction: dict[str, Any] = {"manifestation": [{"text": row.reaction or "Not recorded"}]}
        if row.severity in ("mild", "moderate", "severe"):
            reaction["severity"] = row.severity
        resource["reaction"] = [reaction]
    return resource


CONDITION_CATEGORY = {
    "problem_list": ("problem-list-item", "Problem List Item"),
    "encounter_diagnosis": ("encounter-diagnosis", "Encounter Diagnosis"),
}


def condition(row: Problem) -> Resource:
    wrong = row.clinical_status == "entered_in_error"
    code, display = CONDITION_CATEGORY.get(row.category, ("problem-list-item", "Problem List Item"))
    concept: dict[str, Any] = {"text": row.description}
    if row.code:
        concept["coding"] = [{"system": ICD_10, "code": row.code}]
    resource: Resource = {
        "resourceType": "Condition",
        "id": str(row.id),
        "verificationStatus": _verification("condition-ver-status", wrong),
        "category": [_code(f"{TERMINOLOGY}/condition-category", code, display)],
        "code": concept,
        "subject": ref(row.patient_id),
        "encounter": ref(row.encounter_id),
        "recordedDate": _instant(row.recorded_at),
        "recorder": ref(row.recorded_by_id),
    }
    if not wrong:
        resource["clinicalStatus"] = _clinical_status("condition-clinical", row.clinical_status)
    if row.onset_date:
        resource["onsetDateTime"] = _day(row.onset_date)
    return resource


def medication_request(row: Prescription) -> Resource:
    medicine = f"{row.medicine} {row.strength}" if row.strength else row.medicine
    route = ROUTE_TEXT.get(row.route, row.route)
    words = f"{row.dose}, {route.lower()}, {row.frequency}, for {row.duration}"
    dosage: dict[str, Any] = {
        "text": f"{words}. {row.instructions}" if row.instructions else words,
        "route": {"text": route},
    }
    if row.instructions:
        dosage["patientInstruction"] = row.instructions
    return {
        "resourceType": "MedicationRequest",
        "id": str(row.id),
        "status": _fhir_status(row.clinical_status),
        "intent": "order",
        "medicationCodeableConcept": {"text": medicine},
        "subject": ref(row.patient_id),
        "encounter": ref(row.encounter_id),
        "authoredOn": _instant(row.written_at),
        "requester": ref(row.recorded_by_id),
        "dosageInstruction": [dosage],
    }


def consent(row: Consent, *, organization_id: uuid.UUID, wording_version: int | None) -> Resource:
    provision: dict[str, Any] = {
        "type": "permit",
        "period": {"start": _instant(row.granted_at)},
        "purpose": [{"system": CONSENT_PURPOSE_SYSTEM, "code": row.purpose}],
    }
    if row.revoked_at:
        provision["period"]["end"] = _instant(row.revoked_at)
    resource: Resource = {
        "resourceType": "Consent",
        "id": str(row.id),
        "status": "inactive" if row.revoked_at else "active",
        "scope": _code(f"{TERMINOLOGY}/consentscope", "patient-privacy", "Privacy Consent"),
        "category": [_code(LOINC, "59284-0", "Patient Consent")],
        "patient": ref(row.patient_id),
        "dateTime": _instant(row.granted_at),
        "organization": [ref(organization_id)],
        "provision": provision,
    }
    if wording_version is not None:
        resource["policyRule"] = {"text": f"Clinic consent wording, version {wording_version}"}
    if row.granted_by == "caregiver":
        resource["performer"] = [{"display": "Caregiver, on the patient's behalf"}]
    else:
        resource["performer"] = [ref(row.patient_id)]
    return resource


def bundle(
    resources: list[Resource], *, bundle_id: uuid.UUID, made_at: datetime
) -> Resource:
    """A collection: the resources together, each under its own urn:uuid address."""
    return {
        "resourceType": "Bundle",
        "id": str(bundle_id),
        "meta": {"lastUpdated": _instant(made_at)},
        "identifier": {"system": "urn:ietf:rfc:3986", "value": f"urn:uuid:{bundle_id}"},
        "type": "collection",
        "timestamp": _instant(made_at),
        "entry": [
            {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource}
            for resource in resources
        ],
    }
