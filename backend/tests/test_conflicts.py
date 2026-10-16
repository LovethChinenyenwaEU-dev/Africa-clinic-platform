"""Week 8 Step 3: conflicting corrections are kept, shown, and settled by a clinician (FR-O4)."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.records.chart import (
    ProblemDetails,
    list_patient_problems,
    record_problem,
    resolve_problem_conflict,
    revise_problem,
)
from app.modules.records.conflicts import NotAConflictError
from app.modules.records.notes import (
    NotNoteAuthorError,
    amend_note,
    list_encounter_notes,
    resolve_note_conflict,
    write_note,
)
from app.modules.records.service import (
    EncounterNotOpenError,
    NotAClinicianError,
    mark_entered_in_error,
    open_encounter,
)
from app.modules.records.vitals import (
    NotVitalsAuthorError,
    VitalReadings,
    VitalsNotFoundError,
    correct_vitals,
    list_encounter_vitals,
    record_vitals,
    resolve_vitals_conflict,
)
from tests.scheduling_helpers import PASSWORD, build_clinic

API = "/api/v1"
FEVER = VitalReadings(temperature_c=Decimal("38.4"), pulse_bpm=104)
TABLET_FIX = VitalReadings(temperature_c=Decimal("37.4"), pulse_bpm=88)
PHONE_FIX = VitalReadings(temperature_c=Decimal("38.0"), pulse_bpm=96)


@pytest.fixture
def clinics(session, run_id):
    """Clinic A also has a second doctor who took no part in the visit."""
    data = {label: build_clinic(session, run_id, label) for label in ("a", "b")}
    data["a"]["other_doctor"] = create_staff(
        session,
        tenant_id=data["a"]["tenant"].id,
        email=f"a-other-doctor@{run_id}.example.com",
        full_name="Test other doctor",
        role="doctor",
        password=PASSWORD,
    )
    return data


def who(clinic, person="nurse"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def visit(session, clinic):
    """Opened by the doctor; the nurse helps."""
    return open_encounter(session, **who(clinic, "doctor"), patient_id=clinic["patient"].id)


def vitals_conflict(session, clinic):
    """The nurse corrects the same set on a tablet, then (offline) on a phone."""
    encounter = visit(session, clinic)
    original = record_vitals(session, **who(clinic), encounter_id=encounter.id, readings=FEVER)
    current = correct_vitals(session, **who(clinic), vitals_id=original.id, readings=TABLET_FIX)
    conflict = correct_vitals(session, **who(clinic), vitals_id=original.id, readings=PHONE_FIX)
    return encounter, original, current, conflict


def statuses(rows):
    return {row.id: row.status for row in rows}


def actions(session, clinic, prefix):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [event for event in events if event.action.startswith(prefix)]


# Vitals


def test_a_conflict_is_shown_beside_the_current_set(session, clinics):
    clinic = clinics["a"]
    encounter, original, current, conflict = vitals_conflict(session, clinic)

    shown = list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)
    everything = list_encounter_vitals(
        session, **who(clinic), encounter_id=encounter.id, include_history=True
    )

    assert statuses(shown) == {current.id: "current", conflict.id: "conflict"}
    assert statuses(everything) == {
        original.id: "superseded",
        current.id: "current",
        conflict.id: "conflict",
    }


def test_keeping_the_conflict_makes_it_current(session, clinics):
    clinic = clinics["a"]
    encounter, _, current, conflict = vitals_conflict(session, clinic)

    kept = resolve_vitals_conflict(
        session, **who(clinic), conflict_id=conflict.id, keep_conflict=True
    )

    assert kept.id == conflict.id
    assert kept.status == "current"
    assert kept.temperature_c == Decimal("38.0")
    shown = list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)
    assert statuses(shown) == {conflict.id: "current"}
    session.refresh(current)
    assert current.status == "superseded"  # kept, never deleted


def test_keeping_the_current_set_puts_the_conflict_in_history(session, clinics):
    clinic = clinics["a"]
    encounter, _, current, conflict = vitals_conflict(session, clinic)

    kept = resolve_vitals_conflict(
        session, **who(clinic), conflict_id=conflict.id, keep_conflict=False
    )

    assert kept.id == current.id
    assert kept.status == "current"
    shown = list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)
    assert statuses(shown) == {current.id: "current"}
    session.refresh(conflict)
    assert conflict.status == "superseded"


def test_the_choice_is_in_the_audit_log_with_the_version_kept(session, clinics):
    clinic = clinics["a"]
    _, original, _, conflict = vitals_conflict(session, clinic)

    resolve_vitals_conflict(session, **who(clinic), conflict_id=conflict.id, keep_conflict=True)

    lines = actions(session, clinic, "vitals.resolve")
    assert len(lines) == 1
    assert lines[0].entity_id == conflict.id
    assert lines[0].patient_id == original.patient_id
    assert lines[0].actor_id == clinic["nurse"].id


def test_a_conflict_can_only_be_settled_once(session, clinics):
    clinic = clinics["a"]
    _, _, current, conflict = vitals_conflict(session, clinic)
    resolve_vitals_conflict(session, **who(clinic), conflict_id=conflict.id, keep_conflict=True)

    with pytest.raises(NotAConflictError):
        resolve_vitals_conflict(
            session, **who(clinic), conflict_id=conflict.id, keep_conflict=False
        )
    with pytest.raises(NotAConflictError):
        resolve_vitals_conflict(session, **who(clinic), conflict_id=current.id, keep_conflict=True)
    assert len(actions(session, clinic, "vitals.resolve")) == 1


def test_a_later_correction_of_the_current_set_is_what_the_conflict_faces(session, clinics):
    """original -> tablet fix -> another fix (current). The phone's conflict faces the newest."""
    clinic = clinics["a"]
    _, _, tablet, conflict = vitals_conflict(session, clinic)
    newest = correct_vitals(session, **who(clinic), vitals_id=tablet.id, readings=FEVER)

    resolve_vitals_conflict(session, **who(clinic), conflict_id=conflict.id, keep_conflict=True)

    session.refresh(newest)
    session.refresh(tablet)
    assert newest.status == "superseded"
    assert tablet.status == "superseded"


def test_the_encounter_owner_may_settle_a_nurses_conflict(session, clinics):
    clinic = clinics["a"]
    _, _, current, conflict = vitals_conflict(session, clinic)

    kept = resolve_vitals_conflict(
        session, **who(clinic, "doctor"), conflict_id=conflict.id, keep_conflict=False
    )

    assert kept.id == current.id


def test_an_uninvolved_clinician_cannot_settle_a_vitals_conflict(session, clinics):
    clinic = clinics["a"]
    _, _, _, conflict = vitals_conflict(session, clinic)

    with pytest.raises(NotVitalsAuthorError):
        resolve_vitals_conflict(
            session, **who(clinic, "other_doctor"), conflict_id=conflict.id, keep_conflict=True
        )
    assert actions(session, clinic, "vitals.resolve") == []


def test_front_desk_cannot_settle_a_conflict(session, clinics):
    clinic = clinics["a"]
    _, _, _, conflict = vitals_conflict(session, clinic)

    with pytest.raises(NotAClinicianError):
        resolve_vitals_conflict(
            session, **who(clinic, "desk"), conflict_id=conflict.id, keep_conflict=True
        )


def test_no_choice_in_an_encounter_marked_as_a_mistake(session, clinics):
    clinic = clinics["a"]
    encounter, _, _, conflict = vitals_conflict(session, clinic)
    mark_entered_in_error(session, **who(clinic, "doctor"), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        resolve_vitals_conflict(
            session, **who(clinic), conflict_id=conflict.id, keep_conflict=True
        )


def test_another_clinic_cannot_see_or_settle_the_conflict(session, clinics):
    _, _, _, conflict = vitals_conflict(session, clinics["a"])

    with pytest.raises(VitalsNotFoundError):
        resolve_vitals_conflict(
            session, **who(clinics["b"]), conflict_id=conflict.id, keep_conflict=True
        )


def test_a_replayed_offline_correction_does_not_make_a_second_conflict(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    original = record_vitals(session, **who(clinic), encounter_id=encounter.id, readings=FEVER)
    correct_vitals(session, **who(clinic), vitals_id=original.id, readings=TABLET_FIX)
    phone_id = uuid.uuid4()

    first = correct_vitals(
        session, **who(clinic), vitals_id=original.id, readings=PHONE_FIX, correction_id=phone_id
    )
    again = correct_vitals(
        session, **who(clinic), vitals_id=original.id, readings=PHONE_FIX, correction_id=phone_id
    )

    assert first.id == again.id == phone_id
    shown = list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)
    assert sorted(statuses(shown).values()) == ["conflict", "current"]


# Notes: only the author chooses


def note_conflict(session, clinic):
    encounter = visit(session, clinic)
    note = write_note(
        session, **who(clinic, "doctor"), encounter_id=encounter.id, kind="history", body="One."
    )
    current = amend_note(session, **who(clinic, "doctor"), note_id=note.id, body="Two.")
    conflict = amend_note(session, **who(clinic, "doctor"), note_id=note.id, body="Three.")
    return encounter, current, conflict


def test_both_wordings_are_shown_until_the_author_chooses(session, clinics):
    clinic = clinics["a"]
    encounter, current, conflict = note_conflict(session, clinic)

    shown = list_encounter_notes(session, **who(clinic, "doctor"), encounter_id=encounter.id)
    assert {note.id: note.version_status for note in shown} == {
        current.id: "current",
        conflict.id: "conflict",
    }

    kept = resolve_note_conflict(
        session, **who(clinic, "doctor"), conflict_id=conflict.id, keep_conflict=True
    )

    assert kept.body == "Three."
    shown = list_encounter_notes(session, **who(clinic, "doctor"), encounter_id=encounter.id)
    assert [note.id for note in shown] == [conflict.id]
    assert len(actions(session, clinic, "note.resolve")) == 1


def test_nobody_but_the_author_chooses_a_notes_wording(session, clinics):
    clinic = clinics["a"]
    _, _, conflict = note_conflict(session, clinic)

    for person in ("nurse", "other_doctor"):
        with pytest.raises(NotNoteAuthorError):
            resolve_note_conflict(
                session, **who(clinic, person), conflict_id=conflict.id, keep_conflict=True
            )
    assert actions(session, clinic, "note.resolve") == []


# Allergies and problems: any active clinician chooses


def test_any_clinician_settles_a_problem_conflict(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    malaria = ProblemDetails(description="Malaria")
    original = record_problem(
        session, **who(clinic, "doctor"), encounter_id=encounter.id, details=malaria
    )
    resolved = ProblemDetails(description="Malaria", clinical_status="resolved")
    current = revise_problem(
        session,
        **who(clinic, "doctor"),
        problem_id=original.id,
        encounter_id=encounter.id,
        details=resolved,
    )
    conflict = revise_problem(
        session,
        **who(clinic),
        problem_id=original.id,
        encounter_id=encounter.id,
        details=ProblemDetails(description="Severe malaria"),
    )
    patient = {"patient_id": clinic["patient"].id}

    shown = list_patient_problems(session, **who(clinic, "other_doctor"), **patient)
    assert {row.id: row.version_status for row in shown} == {
        current.id: "current",
        conflict.id: "conflict",
    }

    kept = resolve_problem_conflict(
        session, **who(clinic, "other_doctor"), conflict_id=conflict.id, keep_conflict=False
    )

    assert kept.id == current.id
    shown = list_patient_problems(session, **who(clinic), **patient)
    assert [row.id for row in shown] == [current.id]
    assert len(actions(session, clinic, "problem.resolve")) == 1


# Through the API


def bearer(session, run_id, role):
    token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_settling_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    _, _, _, conflict = vitals_conflict(session, clinics["a"])
    nurse = bearer(session, run_id, "nurse")
    url = f"{API}/vitals/{conflict.id}/resolve"

    wrong = client.post(url, json={"keep": "both"}, headers=nurse)
    desk = client.post(url, json={"keep": "this"}, headers=bearer(session, run_id, "front_desk"))
    first = client.post(url, json={"keep": "this"}, headers=nurse)
    second = client.post(url, json={"keep": "this"}, headers=nurse)

    assert wrong.status_code == 422
    assert desk.status_code == 403
    assert first.status_code == 200
    assert first.json()["id"] == str(conflict.id)
    assert first.json()["status"] == "current"
    assert second.status_code == 409
