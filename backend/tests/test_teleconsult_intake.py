"""Week 9 Step 4: teleconsult intake, consent and the danger-sign screen (FR-C2, FR-C6)."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.consent.service import grant_consent, publish_consent_text
from app.modules.identity.service import login
from app.modules.scheduling.lifecycle import (
    AppointmentNotFoundError,
    cancel_appointment,
    check_in,
    start_consultation,
)
from app.modules.scheduling.service import get_appointment
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.telehealth.intake import (
    ESCALATION_ADVICE,
    InvalidIntakeError,
    NotATeleconsultError,
    TeleconsultConsentMissingError,
    intake_history,
    submit_intake,
    teleconsult_status,
)
from app.modules.telehealth.models import TeleconsultIntake
from tests.scheduling_helpers import NOW, PASSWORD, book, build_clinic

REASON = "Follow-up on blood pressure readings at home."


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def consent_to_remote_care(session, clinic):
    publish_consent_text(
        session, **who(clinic), purpose="teleconsult", body="I agree to remote consultations."
    )
    grant_consent(
        session,
        **who(clinic),
        patient_id=clinic["patient"].id,
        purpose="teleconsult",
        granted_by="patient",
    )


def remote_visit(session, clinic):
    return book(session, clinic, visit_type="teleconsult")


def intake(session, clinic, visit, reason=REASON, red_flags=(), person="desk", now=NOW, **extra):
    return submit_intake(
        session,
        **who(clinic, person),
        appointment_id=visit.id,
        reason=reason,
        red_flags=list(red_flags),
        now=now,
        **extra,
    )


def status_of(session, clinic, visit):
    return get_appointment(session, tenant_id=clinic["tenant"].id, appointment_id=visit.id).status


def actions(session, clinic):
    return [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]


def test_no_danger_sign_puts_the_patient_in_the_remote_waiting_room(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)
    visit = remote_visit(session, clinic)

    taken = intake(session, clinic, visit)

    assert taken.outcome == "ready"
    assert taken.reason == REASON
    assert status_of(session, clinic, visit) == "waiting"
    assert "teleconsult.intake" in actions(session, clinic)
    assert "appointment.check_in" in actions(session, clinic)
    assert "teleconsult.escalate" not in actions(session, clinic)
    # The clinician can now start the remote visit.
    start_consultation(session, **who(clinic, "doctor"), appointment_id=visit.id, now=NOW)
    assert status_of(session, clinic, visit) == "in_consult"


def test_a_danger_sign_escalates_and_the_remote_visit_cannot_go_ahead(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)
    visit = remote_visit(session, clinic)

    taken = intake(session, clinic, visit, red_flags=["chest_pain"])

    assert taken.outcome == "escalated"
    assert taken.red_flags == ["chest_pain"]
    assert status_of(session, clinic, visit) == "booked"  # not in the remote waiting room
    assert "teleconsult.escalate" in actions(session, clinic)
    with pytest.raises(InvalidMoveError):
        check_in(session, **who(clinic), appointment_id=visit.id, now=NOW)
    # Front desk then cancels it and books the patient in person.
    cancel_appointment(session, **who(clinic), appointment_id=visit.id, now=NOW)


def test_a_remote_visit_cannot_be_checked_in_without_its_intake(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit(session, clinic)

    with pytest.raises(InvalidMoveError):
        check_in(session, **who(clinic), appointment_id=visit.id, now=NOW)


def test_in_person_visits_need_no_intake(session, clinics):
    clinic = clinics["a"]
    visit = book(session, clinic)

    check_in(session, **who(clinic), appointment_id=visit.id, now=NOW)

    assert status_of(session, clinic, visit) == "waiting"


def test_no_remote_care_without_consent(session, clinics):
    clinic = clinics["a"]
    visit = remote_visit(session, clinic)

    with pytest.raises(TeleconsultConsentMissingError):
        intake(session, clinic, visit)
    assert session.exec(tenant_select(TeleconsultIntake, clinic["tenant"].id)).all() == []


def test_intake_is_only_for_remote_visits(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)

    with pytest.raises(NotATeleconsultError):
        intake(session, clinic, book(session, clinic))


@pytest.mark.parametrize("reason,flags", [("   ", []), ("x" * 501, []), (REASON, ["feels odd"])])
def test_incomplete_intake_is_refused(session, clinics, reason, flags):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)

    with pytest.raises(InvalidIntakeError):
        intake(session, clinic, remote_visit(session, clinic), reason=reason, red_flags=flags)


def test_no_intake_once_the_visit_is_over_or_cancelled(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)
    visit = remote_visit(session, clinic)
    cancel_appointment(session, **who(clinic), appointment_id=visit.id, now=NOW)

    with pytest.raises(InvalidMoveError):
        intake(session, clinic, visit)


def test_a_re_sent_intake_is_recorded_once(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)
    visit = remote_visit(session, clinic)
    device_id = uuid.uuid4()

    first = intake(session, clinic, visit, intake_id=device_id)
    again = intake(session, clinic, visit, intake_id=device_id)

    assert first.id == again.id == device_id
    assert actions(session, clinic).count("teleconsult.intake") == 1


def test_the_newest_intake_counts_and_the_history_is_kept(session, clinics):
    clinic = clinics["a"]
    consent_to_remote_care(session, clinic)
    visit = remote_visit(session, clinic)
    intake(session, clinic, visit, red_flags=["severe_pain"])
    # The nurse calls back 20 minutes later: the pain was mild after all.
    # (A later time, so "newest" is not a coin toss between two equal timestamps.)
    later = NOW + timedelta(minutes=20)
    intake(session, clinic, visit, person="nurse", reason="Mild back pain, two days.", now=later)

    history = intake_history(session, **who(clinic, "nurse"), appointment_id=visit.id)

    assert [row.outcome for row in history] == ["ready", "escalated"]
    assert status_of(session, clinic, visit) == "waiting"
    assert teleconsult_status(session, tenant_id=clinic["tenant"].id, appointment_id=visit.id) == (
        True,
        "ready",
    )
    assert "teleconsult.intake_view" in actions(session, clinic)


def test_another_clinic_cannot_take_or_read_the_intake(session, clinics):
    consent_to_remote_care(session, clinics["a"])
    visit = remote_visit(session, clinics["a"])

    with pytest.raises(AppointmentNotFoundError):
        intake(session, clinics["b"], visit)
    with pytest.raises(AppointmentNotFoundError):
        intake_history(session, **who(clinics["b"]), appointment_id=visit.id)


def test_intake_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]
    visit = remote_visit(session, clinic)

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    base = f"/api/v1/teleconsults/{visit.id}"
    desk = bearer("front_desk")
    before = client.get(f"{base}/status", headers=desk)
    no_consent = client.post(f"{base}/intake", json={"reason": REASON}, headers=desk)
    consent_to_remote_care(session, clinic)
    escalated = client.post(
        f"{base}/intake",
        json={"reason": REASON, "red_flags": ["difficulty_breathing"]},
        headers=desk,
    )
    desk_reads = client.get(f"{base}/intake", headers=desk)
    nurse_reads = client.get(f"{base}/intake", headers=bearer("nurse"))
    after = client.get(f"{base}/status", headers=desk)

    assert before.json() == {"consented": False, "intake": None}
    assert no_consent.status_code == 409
    assert escalated.status_code == 201
    assert escalated.json()["outcome"] == "escalated"
    assert escalated.json()["advice"] == ESCALATION_ADVICE
    assert "reason" not in escalated.json()
    assert desk_reads.status_code == 403  # the reason is health information
    assert nurse_reads.json()[0]["reason"] == REASON
    assert after.json() == {"consented": True, "intake": "escalated"}
