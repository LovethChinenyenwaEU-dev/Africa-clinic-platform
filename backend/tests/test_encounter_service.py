import uuid
from datetime import date, timedelta

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.patients.service import PatientNotFoundError, create_patient
from app.modules.records.models import Encounter
from app.modules.records.service import (
    EncounterNotFoundError,
    InvalidEncounterMoveError,
    NotAClinicianError,
    NotEncounterOwnerError,
    VisitMismatchError,
    VisitNotFoundError,
    close_encounter,
    get_encounter,
    list_patient_encounters,
    mark_entered_in_error,
    open_encounter,
)
from tests.scheduling_helpers import NOW, book, build_clinic, walk_in


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="nurse"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def start(session, clinic, person="nurse", **changes):
    values = {"patient_id": clinic["patient"].id, "now": NOW}
    return open_encounter(session, **who(clinic, person), **(values | changes))


def stored(session, clinic):
    return session.exec(tenant_select(Encounter, clinic["tenant"].id)).all()


def encounter_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith("encounter."))


def test_a_nurse_opens_an_encounter_for_a_patient_who_has_arrived(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic)

    encounter = start(session, clinic, appointment_id=visit.id)

    assert encounter.status == "open"
    assert encounter.appointment_id == visit.id
    assert encounter.clinician_id == clinic["nurse"].id
    assert encounter.opened_at == NOW
    assert encounter_actions(session, clinic) == ["encounter.create"]


def test_an_encounter_can_be_opened_without_a_visit(session, clinics):
    encounter = start(session, clinics["a"])

    assert encounter.appointment_id is None


def test_the_device_id_is_kept_and_a_replay_creates_nothing_new(session, clinics):
    clinic = clinics["a"]
    device_id = uuid.uuid4()

    first = start(session, clinic, encounter_id=device_id)
    again = start(session, clinic, encounter_id=device_id)

    assert first.id == again.id == device_id
    assert len(stored(session, clinic)) == 1
    assert encounter_actions(session, clinic) == ["encounter.create"]


def test_a_double_tap_on_the_same_visit_returns_the_same_encounter(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic)

    first = start(session, clinic, appointment_id=visit.id)
    again = start(session, clinic, person="doctor", appointment_id=visit.id)

    assert first.id == again.id
    assert len(stored(session, clinic)) == 1


def test_front_desk_cannot_open_an_encounter(session, clinics):
    with pytest.raises(NotAClinicianError):
        start(session, clinics["a"], person="desk")
    assert stored(session, clinics["a"]) == []


def test_an_encounter_waits_until_the_patient_has_arrived(session, clinics):
    clinic = clinics["a"]
    visit = book(session, clinic, starts_at=NOW + timedelta(days=1))

    with pytest.raises(VisitMismatchError):
        start(session, clinic, appointment_id=visit.id)


def test_the_visit_must_belong_to_the_same_patient(session, clinics):
    clinic = clinics["a"]
    visit = walk_in(session, clinic)
    other_patient = create_patient(
        session,
        **who(clinic, "desk"),
        full_name="Test Patient Other",
        date_of_birth=date(1970, 3, 3),
        sex="male",
    )

    with pytest.raises(VisitMismatchError):
        start(session, clinic, patient_id=other_patient.id, appointment_id=visit.id)


def test_another_clinics_patient_or_visit_is_not_found(session, clinics):
    other_visit = walk_in(session, clinics["b"])

    with pytest.raises(PatientNotFoundError):
        start(session, clinics["a"], patient_id=clinics["b"]["patient"].id)
    with pytest.raises(VisitNotFoundError):
        start(session, clinics["a"], appointment_id=other_visit.id)


def test_the_clinician_who_opened_the_encounter_closes_it(session, clinics):
    clinic = clinics["a"]
    encounter = start(session, clinic, person="doctor")
    later = NOW + timedelta(minutes=20)

    closed = close_encounter(
        session, **who(clinic, "doctor"), encounter_id=encounter.id, now=later
    )

    assert closed.status == "closed"
    assert closed.closed_by_id == clinic["doctor"].id
    assert closed.closed_at == later
    assert encounter_actions(session, clinic) == ["encounter.close", "encounter.create"]


@pytest.mark.parametrize("sign_off", [close_encounter, mark_entered_in_error])
def test_another_clinician_cannot_sign_off_someone_elses_encounter(session, clinics, sign_off):
    clinic = clinics["a"]
    encounter = start(session, clinic, person="nurse")

    with pytest.raises(NotEncounterOwnerError):
        sign_off(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    (unchanged,) = stored(session, clinic)
    session.refresh(unchanged)
    assert unchanged.status == "open"
    assert unchanged.closed_by_id is None
    assert encounter_actions(session, clinic) == ["encounter.create"]


def test_a_closed_encounter_is_final(session, clinics):
    clinic = clinics["a"]
    encounter = start(session, clinic)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(InvalidEncounterMoveError):
        close_encounter(session, **who(clinic), encounter_id=encounter.id)
    with pytest.raises(InvalidEncounterMoveError):
        mark_entered_in_error(session, **who(clinic), encounter_id=encounter.id)


def test_a_mistaken_encounter_is_marked_not_deleted(session, clinics):
    clinic = clinics["a"]
    encounter = start(session, clinic)

    marked = mark_entered_in_error(session, **who(clinic), encounter_id=encounter.id)

    assert marked.status == "entered_in_error"
    assert len(stored(session, clinic)) == 1
    with pytest.raises(InvalidEncounterMoveError):
        close_encounter(session, **who(clinic), encounter_id=encounter.id)


def test_front_desk_cannot_close_an_encounter(session, clinics):
    clinic = clinics["a"]
    encounter = start(session, clinic)

    with pytest.raises(NotAClinicianError):
        close_encounter(session, **who(clinic, "desk"), encounter_id=encounter.id)


def test_another_clinic_cannot_close_or_see_an_encounter(session, clinics):
    encounter = start(session, clinics["a"])

    with pytest.raises(EncounterNotFoundError):
        close_encounter(session, **who(clinics["b"]), encounter_id=encounter.id)
    assert get_encounter(session, **who(clinics["b"]), encounter_id=encounter.id) is None
    assert encounter_actions(session, clinics["b"]) == []


def test_viewing_an_encounter_is_written_in_the_diary(session, clinics):
    clinic = clinics["a"]
    encounter = start(session, clinic)

    seen = get_encounter(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    assert seen.id == encounter.id
    assert encounter_actions(session, clinic) == ["encounter.create", "encounter.view"]


def test_a_patients_history_is_newest_first_and_reading_it_is_logged(session, clinics):
    clinic = clinics["a"]
    older = start(session, clinic, now=NOW - timedelta(days=30))
    newer = start(session, clinic, now=NOW)

    history = list_patient_encounters(
        session, **who(clinic, "doctor"), patient_id=clinic["patient"].id
    )

    assert [encounter.id for encounter in history] == [newer.id, older.id]
    assert "encounter.list" in encounter_actions(session, clinic)


def test_another_clinics_patient_history_is_not_found(session, clinics):
    with pytest.raises(PatientNotFoundError):
        list_patient_encounters(
            session, **who(clinics["a"]), patient_id=clinics["b"]["patient"].id
        )
