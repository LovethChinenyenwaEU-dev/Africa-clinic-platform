import uuid

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.records.models import ClinicalNote
from app.modules.records.notes import (
    InvalidNoteError,
    NoteNotFoundError,
    NotNoteAuthorError,
    amend_note,
    clean_body,
    list_encounter_notes,
    write_note,
)
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotAClinicianError,
    NotCurrentVersionError,
    close_encounter,
    mark_entered_in_error,
    open_encounter,
)
from tests.scheduling_helpers import build_clinic

HISTORY = "Fever for 3 days.\nNo cough."
AMENDED = "Fever for 4 days.\nNo cough."

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "encounter_id",
    "patient_id",
    "version_status",
    "replaces_id",
    "kind",
    "body",
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


def visit(session, clinic, person="doctor"):
    return open_encounter(session, **who(clinic, person), patient_id=clinic["patient"].id)


def write(session, clinic, encounter, person="doctor", kind="history", body=HISTORY, **extra):
    return write_note(
        session, **who(clinic, person), encounter_id=encounter.id, kind=kind, body=body, **extra
    )


def stored(session, clinic):
    return session.exec(tenant_select(ClinicalNote, clinic["tenant"].id)).all()


def note_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith("note."))


def test_note_table_columns_are_exactly_these():
    assert set(ClinicalNote.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_the_ends_are_trimmed_but_line_breaks_are_kept():
    assert clean_body("  Fever.\nNo cough.  \n") == "Fever.\nNo cough."


@pytest.mark.parametrize("body", ["", "   \n  ", "x" * 10_001])
def test_empty_or_huge_notes_are_refused(body):
    with pytest.raises(InvalidNoteError):
        clean_body(body)


def test_a_clinician_writes_a_note_in_an_open_visit(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    note = write(session, clinic, encounter)

    assert note.body == HISTORY
    assert note.kind == "history"
    assert note.patient_id == clinic["patient"].id
    assert note.recorded_by_id == clinic["doctor"].id
    assert note.version_status == "current"
    assert note_actions(session, clinic) == ["note.write"]


def test_a_nurse_writes_their_own_note_in_the_doctors_visit(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic, "doctor")

    note = write(session, clinic, encounter, person="nurse", kind="progress", body="Settled.")

    assert note.recorded_by_id == clinic["nurse"].id


def test_a_replay_with_the_device_id_creates_nothing_new(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    device_id = uuid.uuid4()

    first = write(session, clinic, encounter, note_id=device_id)
    again = write(session, clinic, encounter, note_id=device_id)

    assert first.id == again.id == device_id
    assert len(stored(session, clinic)) == 1


def test_an_unknown_kind_saves_nothing(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(InvalidNoteError):
        write(session, clinic, encounter, kind="gossip")
    assert stored(session, clinic) == []
    assert note_actions(session, clinic) == []


def test_front_desk_cannot_write_notes(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    with pytest.raises(NotAClinicianError):
        write(session, clinic, encounter, person="desk")


def test_no_new_notes_after_sign_off(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        write(session, clinic, encounter)


def test_another_clinic_cannot_write_into_an_encounter(session, clinics):
    encounter = visit(session, clinics["a"])

    with pytest.raises(EncounterNotFoundError):
        write(session, clinics["b"], encounter)


def test_an_amendment_is_a_new_version_and_the_old_wording_stays(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = write(session, clinic, encounter)

    amended = amend_note(session, **who(clinic), note_id=original.id, body=AMENDED)

    session.refresh(original)
    assert original.version_status == "superseded"
    assert original.body == HISTORY  # untouched
    assert amended.body == AMENDED
    assert amended.kind == original.kind
    assert amended.replaces_id == original.id
    assert note_actions(session, clinic) == ["note.amend", "note.write"]


@pytest.mark.parametrize("person", ["nurse", "doctor"])
def test_nobody_can_amend_someone_elses_note_not_even_the_visit_owner(session, clinics, person):
    clinic = clinics["a"]
    encounter = visit(session, clinic, "doctor")
    author = "doctor" if person == "nurse" else "nurse"
    original = write(session, clinic, encounter, person=author)

    with pytest.raises(NotNoteAuthorError):
        amend_note(session, **who(clinic, person), note_id=original.id, body=AMENDED)
    session.rollback()
    session.refresh(original)
    assert original.version_status == "current"


def test_the_author_may_amend_after_sign_off(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = write(session, clinic, encounter)
    close_encounter(session, **who(clinic), encounter_id=encounter.id)

    amended = amend_note(session, **who(clinic), note_id=original.id, body=AMENDED)

    assert amended.version_status == "current"


def test_notes_in_a_mistaken_encounter_cannot_be_amended(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = write(session, clinic, encounter)
    mark_entered_in_error(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        amend_note(session, **who(clinic), note_id=original.id, body=AMENDED)


def test_amending_an_old_wording_keeps_both_as_a_conflict(session, clinics):
    """Week 8 (FR-O4): the author amended on two devices. Neither wording is lost."""
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = write(session, clinic, encounter)
    first = amend_note(session, **who(clinic), note_id=original.id, body=AMENDED)

    second = amend_note(session, **who(clinic), note_id=original.id, body="Third try.")

    assert second.version_status == "conflict"
    session.refresh(first)
    assert first.version_status == "current"

    # A conflict cannot be amended again: it must be settled first.
    with pytest.raises(NotCurrentVersionError):
        amend_note(session, **who(clinic), note_id=second.id, body="Fourth try.")


def test_another_clinic_cannot_amend_a_note(session, clinics):
    encounter = visit(session, clinics["a"])
    original = write(session, clinics["a"], encounter)

    with pytest.raises(NoteNotFoundError):
        amend_note(session, **who(clinics["b"]), note_id=original.id, body=AMENDED)


def test_reading_notes_shows_the_newest_wording_and_is_logged(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = write(session, clinic, encounter)
    amended = amend_note(session, **who(clinic), note_id=original.id, body=AMENDED)

    current = list_encounter_notes(session, **who(clinic, "nurse"), encounter_id=encounter.id)
    history = list_encounter_notes(
        session, **who(clinic, "nurse"), encounter_id=encounter.id, include_history=True
    )

    assert [note.id for note in current] == [amended.id]
    assert {note.id for note in history} == {original.id, amended.id}
    assert note_actions(session, clinic).count("note.view") == 2


def test_another_clinic_cannot_read_notes(session, clinics):
    encounter = visit(session, clinics["a"])
    write(session, clinics["a"], encounter)

    with pytest.raises(EncounterNotFoundError):
        list_encounter_notes(session, **who(clinics["b"]), encounter_id=encounter.id)
    assert note_actions(session, clinics["b"]) == []
