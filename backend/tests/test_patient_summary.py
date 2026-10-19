"""Week 9 Step 7: the patient summary, drafted by a clinician and approved by the owner (FR-R4)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.records.service import (
    EncounterNotOpenError,
    NotAClinicianError,
    NotEncounterOwnerError,
    close_encounter,
    mark_entered_in_error,
    open_encounter,
)
from app.modules.records.summary import (
    InvalidSummaryError,
    NotSummaryAuthorError,
    SummaryMoveError,
    SummaryNotFoundError,
    approve_summary,
    approved_summaries_for_patient,
    draft_summary,
    edit_draft,
    list_encounter_summaries,
    withdraw_summary,
)
from tests.scheduling_helpers import PASSWORD, build_clinic

TEXT = "Your visit today\n\nWhat we found:\n- Malaria\n\nYour medicines:\n- Paracetamol"


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def visit(session, clinic):
    """Opened by the doctor, who owns it."""
    return open_encounter(session, **who(clinic), patient_id=clinic["patient"].id)


def draft(session, clinic, encounter, person="doctor", body=TEXT, **extra):
    return draft_summary(
        session, **who(clinic, person), encounter_id=encounter.id, body=body, **extra
    )


def sign_off(session, clinic, encounter):
    close_encounter(session, **who(clinic), encounter_id=encounter.id)


def actions(session, clinic):
    return [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]


def readable_by_patient(session, clinic):
    return approved_summaries_for_patient(
        session, tenant_id=clinic["tenant"].id, patient_id=clinic["patient"].id
    )


def test_a_draft_keeps_its_line_breaks_and_is_not_for_the_patient(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    written = draft(session, clinic, encounter, person="nurse", body=f"  {TEXT}  ")

    assert written.body == TEXT
    assert written.status == "draft"
    assert readable_by_patient(session, clinic) == []
    assert "summary.draft" in actions(session, clinic)


@pytest.mark.parametrize("body", ["   ", "x" * 4001])
def test_empty_or_huge_summaries_are_refused(session, clinics, body):
    with pytest.raises(InvalidSummaryError):
        draft(session, clinics["a"], visit(session, clinics["a"]), body=body)


def test_front_desk_cannot_draft(session, clinics):
    with pytest.raises(NotAClinicianError):
        draft(session, clinics["a"], visit(session, clinics["a"]), person="desk")


def test_only_the_author_edits_a_draft(session, clinics):
    clinic = clinics["a"]
    written = draft(session, clinic, visit(session, clinic), person="nurse")

    edited = edit_draft(session, **who(clinic, "nurse"), summary_id=written.id, body="Better.")

    assert edited.body == "Better."
    with pytest.raises(NotSummaryAuthorError):
        edit_draft(session, **who(clinic), summary_id=written.id, body="Mine now.")


def test_one_summary_at_a_time_per_visit(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    draft(session, clinic, encounter)

    with pytest.raises(SummaryMoveError):
        draft(session, clinic, encounter, person="nurse")


def test_a_re_sent_draft_is_saved_once(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    device_id = uuid.uuid4()

    first = draft(session, clinic, encounter, summary_id=device_id)
    again = draft(session, clinic, encounter, summary_id=device_id)

    assert first.id == again.id == device_id


def test_approval_waits_for_sign_off_and_comes_from_the_owner(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    written = draft(session, clinic, encounter, person="nurse")

    with pytest.raises(SummaryMoveError):  # not signed off yet
        approve_summary(session, **who(clinic), summary_id=written.id)
    sign_off(session, clinic, encounter)
    with pytest.raises(NotEncounterOwnerError):  # the nurse wrote it, but does not own the visit
        approve_summary(session, **who(clinic, "nurse"), summary_id=written.id)

    approved = approve_summary(session, **who(clinic), summary_id=written.id)

    assert approved.status == "approved"
    assert approved.approved_by_id == clinic["doctor"].id
    assert [row.id for row in readable_by_patient(session, clinic)] == [written.id]
    assert "summary.approve" in actions(session, clinic)


def test_an_approved_summary_never_changes(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    written = draft(session, clinic, encounter)
    sign_off(session, clinic, encounter)
    approve_summary(session, **who(clinic), summary_id=written.id)

    with pytest.raises(SummaryMoveError):
        edit_draft(session, **who(clinic), summary_id=written.id, body="Changed.")
    with pytest.raises(SummaryMoveError):
        approve_summary(session, **who(clinic), summary_id=written.id)


def test_withdrawing_hides_it_from_the_patient_and_allows_a_new_one(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    wrong = draft(session, clinic, encounter, body="Wrong medicine listed.")
    sign_off(session, clinic, encounter)
    approve_summary(session, **who(clinic), summary_id=wrong.id)

    with pytest.raises(NotEncounterOwnerError):
        withdraw_summary(session, **who(clinic, "nurse"), summary_id=wrong.id)
    withdrawn = withdraw_summary(session, **who(clinic), summary_id=wrong.id)
    corrected = draft(session, clinic, encounter, body="Correct medicine.")

    assert withdrawn.status == "withdrawn"
    assert readable_by_patient(session, clinic) == []
    history = list_encounter_summaries(session, **who(clinic), encounter_id=encounter.id)
    assert [row.id for row in history] == [corrected.id, wrong.id]  # kept, newest first
    assert "summary.view" in actions(session, clinic)
    with pytest.raises(SummaryMoveError):  # a draft cannot be withdrawn: just edit it
        withdraw_summary(session, **who(clinic), summary_id=corrected.id)


def test_no_summary_for_an_encounter_opened_by_mistake(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    mark_entered_in_error(session, **who(clinic), encounter_id=encounter.id)

    with pytest.raises(EncounterNotOpenError):
        draft(session, clinic, encounter)


def test_another_clinic_cannot_touch_a_summary(session, clinics):
    clinic = clinics["a"]
    written = draft(session, clinic, visit(session, clinic))

    with pytest.raises(SummaryNotFoundError):
        edit_draft(session, **who(clinics["b"]), summary_id=written.id, body="x")
    assert approved_summaries_for_patient(
        session, tenant_id=clinics["b"]["tenant"].id, patient_id=clinic["patient"].id
    ) == []


def test_the_summary_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    doctor = bearer("doctor")
    started = client.post(
        f"/api/v1/encounters/{encounter.id}/summaries", json={"body": TEXT}, headers=doctor
    )
    summary_id = started.json()["id"]
    too_early = client.post(f"/api/v1/summaries/{summary_id}/approve", headers=doctor)
    sign_off(session, clinic, encounter)
    approved = client.post(f"/api/v1/summaries/{summary_id}/approve", headers=doctor)
    by_desk = client.get(
        f"/api/v1/encounters/{encounter.id}/summaries", headers=bearer("front_desk")
    )

    assert started.status_code == 201
    assert too_early.status_code == 409
    assert approved.json()["status"] == "approved"
    assert by_desk.status_code == 403
