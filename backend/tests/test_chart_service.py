import uuid
from datetime import date

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.patients.service import PatientNotFoundError, create_patient
from app.modules.records.chart import (
    AllergyDetails,
    AllergyNotFoundError,
    InvalidChartEntryError,
    ProblemDetails,
    WrongPatientError,
    list_patient_allergies,
    list_patient_problems,
    record_allergy,
    record_problem,
    revise_allergy,
    revise_problem,
)
from app.modules.records.models import Allergy, Problem
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotAClinicianError,
    NotCurrentVersionError,
    close_encounter,
    open_encounter,
)
from tests.scheduling_helpers import build_clinic

PENICILLIN = AllergyDetails(substance="Penicillin", reaction="Rash", severity="moderate")
OUTGROWN = AllergyDetails(substance="Penicillin", reaction="Rash", clinical_status="inactive")
MALARIA = ProblemDetails(
    description="Uncomplicated malaria", category="encounter_diagnosis", code="B54"
)


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def visit(session, clinic, person="doctor"):
    return open_encounter(session, **who(clinic, person), patient_id=clinic["patient"].id)


def stored(session, clinic, model):
    return session.exec(tenant_select(model, clinic["tenant"].id)).all()


def actions(session, clinic, prefix):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith(prefix))


def test_an_allergy_recorded_in_a_visit_belongs_to_the_patient(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    allergy = record_allergy(
        session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN
    )

    assert allergy.patient_id == clinic["patient"].id
    assert allergy.encounter_id == encounter.id
    assert allergy.version_status == "current"
    assert allergy.clinical_status == "active"
    assert allergy.recorded_by_id == clinic["doctor"].id
    assert actions(session, clinic, "allergy.") == ["allergy.record"]


def test_a_nurse_can_add_to_the_list_in_a_doctors_open_visit(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic, "doctor")

    allergy = record_allergy(
        session, **who(clinic, "nurse"), encounter_id=encounter.id, details=PENICILLIN
    )

    assert allergy.recorded_by_id == clinic["nurse"].id


def test_a_replay_with_the_device_id_creates_nothing_new(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    device_id = uuid.uuid4()

    first = record_allergy(
        session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN, allergy_id=device_id
    )
    again = record_allergy(
        session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN, allergy_id=device_id
    )

    assert first.id == again.id == device_id
    assert len(stored(session, clinic, Allergy)) == 1


def test_front_desk_cannot_record_allergies_or_problems(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(NotAClinicianError):
        record_allergy(
            session, **who(clinic, "desk"), encounter_id=encounter.id, details=PENICILLIN
        )
    with pytest.raises(NotAClinicianError):
        record_problem(session, **who(clinic, "desk"), encounter_id=encounter.id, details=MALARIA)


def test_bad_details_save_nothing(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(InvalidChartEntryError):
        record_allergy(
            session, **who(clinic), encounter_id=encounter.id, details=AllergyDetails(" ")
        )
    assert stored(session, clinic, Allergy) == []
    assert actions(session, clinic, "allergy.") == []


def test_nothing_new_goes_into_a_signed_off_visit(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        record_allergy(session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN)


def test_another_clinic_cannot_write_into_an_encounter(session, clinics):
    encounter = visit(session, clinics["a"])

    with pytest.raises(EncounterNotFoundError):
        record_problem(session, **who(clinics["b"]), encounter_id=encounter.id, details=MALARIA)


def test_a_change_at_a_later_visit_is_a_new_version_and_the_old_one_stays(session, clinics):
    clinic = clinics["a"]
    first_visit = visit(session, clinic)
    original = record_allergy(
        session, **who(clinic), encounter_id=first_visit.id, details=PENICILLIN
    )
    close_encounter(session, **who(clinic), encounter_id=first_visit.id)
    later_visit = visit(session, clinic, "nurse")

    revised = revise_allergy(
        session,
        **who(clinic, "nurse"),
        allergy_id=original.id,
        encounter_id=later_visit.id,
        details=OUTGROWN,
    )

    session.refresh(original)
    assert original.version_status == "superseded"
    assert original.clinical_status == "active"  # untouched
    assert revised.replaces_id == original.id
    assert revised.encounter_id == later_visit.id
    assert revised.clinical_status == "inactive"
    assert revised.recorded_by_id == clinic["nurse"].id
    assert actions(session, clinic, "allergy.") == ["allergy.record", "allergy.revise"]


def test_a_change_must_be_made_in_a_visit_of_the_same_patient(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = record_allergy(session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN)
    someone_else = create_patient(
        session,
        **who(clinic, "desk"),
        full_name="Test Patient Someone Else",
        date_of_birth=date(1960, 6, 6),
        sex="female",
    )
    their_visit = open_encounter(session, **who(clinic), patient_id=someone_else.id)

    with pytest.raises(WrongPatientError):
        revise_allergy(
            session,
            **who(clinic),
            allergy_id=original.id,
            encounter_id=their_visit.id,
            details=OUTGROWN,
        )


def test_only_the_newest_version_can_be_changed(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = record_allergy(session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN)
    revise_allergy(
        session, **who(clinic), allergy_id=original.id, encounter_id=encounter.id, details=OUTGROWN
    )

    with pytest.raises(NotCurrentVersionError):
        revise_allergy(
            session,
            **who(clinic),
            allergy_id=original.id,
            encounter_id=encounter.id,
            details=PENICILLIN,
        )


def test_another_clinic_cannot_change_an_allergy(session, clinics):
    encounter = visit(session, clinics["a"])
    original = record_allergy(
        session, **who(clinics["a"]), encounter_id=encounter.id, details=PENICILLIN
    )
    their_visit = visit(session, clinics["b"])

    with pytest.raises(AllergyNotFoundError):
        revise_allergy(
            session,
            **who(clinics["b"]),
            allergy_id=original.id,
            encounter_id=their_visit.id,
            details=OUTGROWN,
        )


def test_a_diagnosis_is_recorded_and_resolved_as_versions(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    diagnosis = record_problem(session, **who(clinic), encounter_id=encounter.id, details=MALARIA)

    resolved = revise_problem(
        session,
        **who(clinic),
        problem_id=diagnosis.id,
        encounter_id=encounter.id,
        details=ProblemDetails(
            description="Uncomplicated malaria",
            category="encounter_diagnosis",
            code="B54",
            clinical_status="resolved",
        ),
    )

    assert diagnosis.code == "B54"
    assert resolved.clinical_status == "resolved"
    assert resolved.replaces_id == diagnosis.id
    assert len(stored(session, clinic, Problem)) == 2
    assert actions(session, clinic, "problem.") == ["problem.record", "problem.revise"]


def test_the_list_shows_current_entries_and_hides_mistakes_unless_history_is_asked(
    session, clinics
):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    kept = record_allergy(session, **who(clinic), encounter_id=encounter.id, details=PENICILLIN)
    mistake = record_allergy(
        session, **who(clinic), encounter_id=encounter.id, details=AllergyDetails("Peanuts")
    )
    marked = revise_allergy(
        session,
        **who(clinic),
        allergy_id=mistake.id,
        encounter_id=encounter.id,
        details=AllergyDetails("Peanuts", clinical_status="entered_in_error"),
    )
    patient_id = clinic["patient"].id

    current = list_patient_allergies(session, **who(clinic), patient_id=patient_id)
    history = list_patient_allergies(
        session, **who(clinic), patient_id=patient_id, include_history=True
    )

    assert [allergy.id for allergy in current] == [kept.id]
    assert {allergy.id for allergy in history} == {kept.id, mistake.id, marked.id}
    assert actions(session, clinic, "allergy.").count("allergy.view") == 2


def test_reading_the_problem_list_is_logged(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    record_problem(session, **who(clinic), encounter_id=encounter.id, details=MALARIA)

    problems = list_patient_problems(
        session, **who(clinic, "nurse"), patient_id=clinic["patient"].id
    )

    assert [problem.code for problem in problems] == ["B54"]
    assert "problem.view" in actions(session, clinic, "problem.")


def test_another_clinics_patient_lists_are_not_found(session, clinics):
    other_patient = clinics["b"]["patient"].id

    with pytest.raises(PatientNotFoundError):
        list_patient_allergies(session, **who(clinics["a"]), patient_id=other_patient)
    with pytest.raises(PatientNotFoundError):
        list_patient_problems(session, **who(clinics["a"]), patient_id=other_patient)
    assert actions(session, clinics["a"], "allergy.") == []
