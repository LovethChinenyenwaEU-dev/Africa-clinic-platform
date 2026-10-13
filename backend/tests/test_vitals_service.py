import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.records.models import VitalSigns
from app.modules.records.service import (
    EncounterNotFoundError,
    NotAClinicianError,
    close_encounter,
    mark_entered_in_error,
    open_encounter,
)
from app.modules.records.vitals import (
    EncounterNotOpenError,
    InvalidVitalsError,
    NotCurrentVersionError,
    NotVitalsAuthorError,
    VitalReadings,
    VitalsNotFoundError,
    correct_vitals,
    list_encounter_vitals,
    record_vitals,
)
from tests.scheduling_helpers import NOW, build_clinic

FEVER = VitalReadings(temperature_c=Decimal("38.4"), pulse_bpm=104)
FIXED = VitalReadings(temperature_c=Decimal("37.4"), pulse_bpm=88)


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="nurse"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def doctors_encounter(session, clinic):
    """Opened by the doctor, so the nurse is a helper and the doctor is the owner."""
    return open_encounter(session, **who(clinic, "doctor"), patient_id=clinic["patient"].id)


def record(session, clinic, encounter, person="nurse", readings=FEVER, **extra):
    return record_vitals(
        session, **who(clinic, person), encounter_id=encounter.id, readings=readings, **extra
    )


def stored(session, clinic):
    return session.exec(tenant_select(VitalSigns, clinic["tenant"].id)).all()


def vitals_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith("vitals."))


def test_a_nurse_records_vitals_in_the_doctors_open_encounter(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)

    vitals = record(session, clinic, encounter)

    assert vitals.status == "current"
    assert vitals.patient_id == clinic["patient"].id
    assert vitals.recorded_by_id == clinic["nurse"].id
    assert vitals.temperature_c == Decimal("38.4")
    assert vitals.pulse_bpm == 104
    assert vitals_actions(session, clinic) == ["vitals.record"]


def test_vitals_taken_offline_keep_their_time_and_device_id(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    device_id = uuid.uuid4()
    taken = NOW - timedelta(hours=2)

    first = record(session, clinic, encounter, vitals_id=device_id, measured_at=taken, now=NOW)
    again = record(session, clinic, encounter, vitals_id=device_id, measured_at=taken, now=NOW)

    assert first.id == again.id == device_id
    assert first.measured_at == taken
    assert len(stored(session, clinic)) == 1
    assert vitals_actions(session, clinic) == ["vitals.record"]


def test_vitals_cannot_be_dated_in_the_future(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)

    with pytest.raises(InvalidVitalsError):
        record(session, clinic, encounter, measured_at=NOW + timedelta(hours=1), now=NOW)


def test_a_mistyped_reading_saves_nothing(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)

    with pytest.raises(InvalidVitalsError):
        record(session, clinic, encounter, readings=VitalReadings(temperature_c=Decimal("370")))
    assert stored(session, clinic) == []
    assert vitals_actions(session, clinic) == []


def test_front_desk_cannot_record_vitals(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)

    with pytest.raises(NotAClinicianError):
        record(session, clinic, encounter, person="desk")


def test_a_signed_off_encounter_takes_no_new_vitals(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    close_encounter(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        record(session, clinic, encounter)


def test_another_clinic_cannot_add_vitals_to_an_encounter(session, clinics):
    encounter = doctors_encounter(session, clinics["a"])

    with pytest.raises(EncounterNotFoundError):
        record(session, clinics["b"], encounter)


def test_a_correction_is_a_new_version_and_the_old_numbers_never_change(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter)

    corrected = correct_vitals(
        session, **who(clinic, "nurse"), vitals_id=original.id, readings=FIXED
    )

    session.refresh(original)
    assert original.status == "superseded"
    assert original.temperature_c == Decimal("38.4")  # untouched
    assert corrected.status == "current"
    assert corrected.replaces_id == original.id
    assert corrected.temperature_c == Decimal("37.4")
    assert corrected.measured_at == original.measured_at
    assert vitals_actions(session, clinic) == ["vitals.correct", "vitals.record"]


def test_the_encounter_owner_may_correct_a_helpers_vitals(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter, person="nurse")

    corrected = correct_vitals(
        session, **who(clinic, "doctor"), vitals_id=original.id, readings=FIXED
    )

    assert corrected.recorded_by_id == clinic["doctor"].id


def test_another_clinician_cannot_correct_someone_elses_vitals(session, clinics):
    clinic = clinics["a"]
    encounter = open_encounter(session, **who(clinic, "nurse"), patient_id=clinic["patient"].id)
    original = record(session, clinic, encounter, person="nurse")

    with pytest.raises(NotVitalsAuthorError):
        correct_vitals(session, **who(clinic, "doctor"), vitals_id=original.id, readings=FIXED)
    session.rollback()
    session.refresh(original)
    assert original.status == "current"


def test_corrections_are_allowed_after_sign_off(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter, person="doctor")
    close_encounter(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    corrected = correct_vitals(
        session, **who(clinic, "doctor"), vitals_id=original.id, readings=FIXED
    )

    assert corrected.status == "current"


def test_only_the_newest_version_can_be_corrected(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter)
    correct_vitals(session, **who(clinic), vitals_id=original.id, readings=FIXED)

    with pytest.raises(NotCurrentVersionError):
        correct_vitals(session, **who(clinic), vitals_id=original.id, readings=FEVER)


def test_a_replayed_correction_creates_nothing_new(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter)
    correction_id = uuid.uuid4()

    first = correct_vitals(
        session, **who(clinic), vitals_id=original.id, readings=FIXED, correction_id=correction_id
    )
    again = correct_vitals(
        session, **who(clinic), vitals_id=original.id, readings=FIXED, correction_id=correction_id
    )

    assert first.id == again.id == correction_id
    assert len(stored(session, clinic)) == 2


def test_vitals_in_a_mistaken_encounter_cannot_be_corrected(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter, person="doctor")
    mark_entered_in_error(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        correct_vitals(session, **who(clinic, "doctor"), vitals_id=original.id, readings=FIXED)


def test_another_clinic_cannot_correct_vitals(session, clinics):
    encounter = doctors_encounter(session, clinics["a"])
    original = record(session, clinics["a"], encounter)

    with pytest.raises(VitalsNotFoundError):
        correct_vitals(session, **who(clinics["b"]), vitals_id=original.id, readings=FIXED)


def test_reading_vitals_shows_current_versions_and_is_logged(session, clinics):
    clinic = clinics["a"]
    encounter = doctors_encounter(session, clinic)
    original = record(session, clinic, encounter)
    corrected = correct_vitals(session, **who(clinic), vitals_id=original.id, readings=FIXED)

    current = list_encounter_vitals(session, **who(clinic, "doctor"), encounter_id=encounter.id)
    history = list_encounter_vitals(
        session, **who(clinic, "doctor"), encounter_id=encounter.id, include_history=True
    )

    assert [vitals.id for vitals in current] == [corrected.id]
    assert {vitals.id for vitals in history} == {original.id, corrected.id}
    assert vitals_actions(session, clinic).count("vitals.view") == 2


def test_another_clinic_cannot_read_an_encounters_vitals(session, clinics):
    encounter = doctors_encounter(session, clinics["a"])
    record(session, clinics["a"], encounter)

    with pytest.raises(EncounterNotFoundError):
        list_encounter_vitals(session, **who(clinics["b"]), encounter_id=encounter.id)
    assert vitals_actions(session, clinics["b"]) == []
