"""Every clinical diary line says exactly which record was touched."""
from decimal import Decimal

import pytest

from app.modules.audit.service import list_audit_events
from app.modules.records.chart import (
    AllergyDetails,
    ProblemDetails,
    list_patient_allergies,
    record_allergy,
    record_problem,
    revise_allergy,
)
from app.modules.records.notes import amend_note, list_encounter_notes, write_note
from app.modules.records.service import close_encounter, get_encounter, open_encounter
from app.modules.records.vitals import (
    VitalReadings,
    correct_vitals,
    list_encounter_vitals,
    record_vitals,
)
from tests.scheduling_helpers import build_clinic


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "ent")


def who(clinic):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic["doctor"].id}


def entity_of(session, clinic, action):
    """The entity on the newest diary line with this action."""
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return next(event.entity_id for event in events if event.action == action)


def test_encounter_lines_name_the_encounter(session, clinic):
    encounter = open_encounter(session, **who(clinic), patient_id=clinic["patient"].id)
    get_encounter(session, **who(clinic), encounter_id=encounter.id)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    for action in ("encounter.create", "encounter.view", "encounter.close"):
        assert entity_of(session, clinic, action) == encounter.id


def test_vitals_lines_name_the_exact_version(session, clinic):
    encounter = open_encounter(session, **who(clinic), patient_id=clinic["patient"].id)
    first = record_vitals(
        session, **who(clinic), encounter_id=encounter.id, readings=VitalReadings(pulse_bpm=90)
    )
    fixed = correct_vitals(
        session,
        **who(clinic),
        vitals_id=first.id,
        readings=VitalReadings(temperature_c=Decimal("37.5")),
    )
    list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)

    assert entity_of(session, clinic, "vitals.record") == first.id
    assert entity_of(session, clinic, "vitals.correct") == fixed.id
    assert entity_of(session, clinic, "vitals.view") == encounter.id


def test_allergy_and_problem_lines_name_the_entry(session, clinic):
    encounter = open_encounter(session, **who(clinic), patient_id=clinic["patient"].id)
    allergy = record_allergy(
        session, **who(clinic), encounter_id=encounter.id, details=AllergyDetails("Penicillin")
    )
    revised = revise_allergy(
        session,
        **who(clinic),
        allergy_id=allergy.id,
        encounter_id=encounter.id,
        details=AllergyDetails("Penicillin", clinical_status="inactive"),
    )
    problem = record_problem(
        session, **who(clinic), encounter_id=encounter.id, details=ProblemDetails("Malaria")
    )
    list_patient_allergies(session, **who(clinic), patient_id=clinic["patient"].id)

    assert entity_of(session, clinic, "allergy.record") == allergy.id
    assert entity_of(session, clinic, "allergy.revise") == revised.id
    assert entity_of(session, clinic, "problem.record") == problem.id
    # A whole-list read touches the patient's list, not one entry: the patient is enough.
    assert entity_of(session, clinic, "allergy.view") is None


def test_note_lines_name_the_note(session, clinic):
    encounter = open_encounter(session, **who(clinic), patient_id=clinic["patient"].id)
    note = write_note(
        session, **who(clinic), encounter_id=encounter.id, kind="history", body="Fever."
    )
    amended = amend_note(session, **who(clinic), note_id=note.id, body="High fever.")
    list_encounter_notes(session, **who(clinic), encounter_id=encounter.id)

    assert entity_of(session, clinic, "note.write") == note.id
    assert entity_of(session, clinic, "note.amend") == amended.id
    assert entity_of(session, clinic, "note.view") == encounter.id
