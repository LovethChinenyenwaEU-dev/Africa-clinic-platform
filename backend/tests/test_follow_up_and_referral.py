"""Week 9 Step 6: follow-up and referral at the end of a consultation (FR-C5)."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.records.outcomes import (
    FollowUpNotFoundError,
    InvalidOutcomeError,
    NotReferralAuthorError,
    OutcomeMoveError,
    ReferralNotFoundError,
    cancel_follow_up,
    cancel_referral,
    follow_ups_due,
    get_referral,
    list_encounter_follow_ups,
    mark_follow_up_booked,
    plan_follow_up,
    write_referral,
)
from app.modules.records.service import (
    EncounterNotOpenError,
    NotAClinicianError,
    close_encounter,
    open_encounter,
)
from tests.scheduling_helpers import PASSWORD, book, build_clinic

TODAY = datetime.now(UTC).date()
IN_TWO_WEEKS = TODAY + timedelta(days=14)
REASON = "Persistent chest pain on exertion.\nECG and echo, please."


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="doctor"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def visit(session, clinic, **extra):
    return open_encounter(session, **who(clinic), patient_id=clinic["patient"].id, **extra)


def follow_up(session, clinic, encounter, person="doctor", **changes):
    values = {"due_date": IN_TWO_WEEKS, "visit_type": "in_person", "instructions": "Repeat BP."}
    return plan_follow_up(
        session, **who(clinic, person), encounter_id=encounter.id, **(values | changes)
    )


def referral(session, clinic, encounter, person="doctor", **changes):
    values = {"to_name": "LUTH Cardiology clinic", "reason": REASON, "urgency": "urgent"}
    return write_referral(
        session, **who(clinic, person), encounter_id=encounter.id, **(values | changes)
    )


def actions(session, clinic):
    return [e.action for e in list_audit_events(session, tenant_id=clinic["tenant"].id)]


# Follow-up


def test_a_clinician_plans_a_follow_up(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    planned = follow_up(session, clinic, encounter, person="nurse", visit_type="teleconsult")

    assert planned.status == "planned"
    assert planned.visit_type == "teleconsult"
    assert planned.patient_id == clinic["patient"].id
    assert "follow_up.plan" in actions(session, clinic)


@pytest.mark.parametrize(
    "changes",
    [
        {"due_date": TODAY - timedelta(days=1)},
        {"due_date": TODAY + timedelta(days=400)},
        {"visit_type": "home_visit"},
        {"instructions": "x" * 501},
    ],
)
def test_impossible_follow_ups_are_refused(session, clinics, changes):
    with pytest.raises(InvalidOutcomeError):
        follow_up(session, clinics["a"], visit(session, clinics["a"]), **changes)


def test_front_desk_cannot_plan_a_follow_up(session, clinics):
    with pytest.raises(NotAClinicianError):
        follow_up(session, clinics["a"], visit(session, clinics["a"]), person="desk")


def test_a_follow_up_written_offline_before_sign_off_is_kept_and_marked_late(session, clinics):
    clinic = clinics["a"]
    now = datetime.now(UTC)
    encounter = visit(session, clinic, now=now - timedelta(hours=2))
    close_encounter(session, **who(clinic), encounter_id=encounter.id, now=now - timedelta(hours=1))

    with pytest.raises(EncounterNotOpenError):
        follow_up(session, clinic, encounter)
    late = follow_up(session, clinic, encounter, written_at=now - timedelta(minutes=90))

    assert late.synced_late is True


def test_a_re_sent_follow_up_is_saved_once(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    device_id = uuid.uuid4()

    first = follow_up(session, clinic, encounter, follow_up_id=device_id)
    again = follow_up(session, clinic, encounter, follow_up_id=device_id)

    assert first.id == again.id == device_id
    assert len(list_encounter_follow_ups(session, **who(clinic), encounter_id=encounter.id)) == 1


def test_front_desk_sees_who_is_due_soonest_first(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    later = follow_up(session, clinic, encounter, due_date=TODAY + timedelta(days=20))
    sooner = follow_up(session, clinic, encounter, due_date=TODAY + timedelta(days=3))
    follow_up(session, clinic, encounter, due_date=TODAY + timedelta(days=60))  # not yet due

    due = follow_ups_due(session, **who(clinic, "desk"), until=TODAY + timedelta(days=30))

    assert [row.id for row, _ in due] == [sooner.id, later.id]
    assert {name for _, name in due} == {"Test Patient A"}
    assert "follow_up.list" in actions(session, clinic)


def test_booking_or_cancelling_takes_it_off_the_list_once(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)
    booked = follow_up(session, clinic, encounter)
    declined = follow_up(session, clinic, encounter)
    appointment = book(session, clinic)

    mark_follow_up_booked(
        session, **who(clinic, "desk"), follow_up_id=booked.id, appointment_id=appointment.id
    )
    cancel_follow_up(session, **who(clinic, "desk"), follow_up_id=declined.id)

    assert follow_ups_due(session, **who(clinic, "desk"), until=IN_TWO_WEEKS) == []
    with pytest.raises(OutcomeMoveError):
        cancel_follow_up(session, **who(clinic, "desk"), follow_up_id=booked.id)


def test_a_follow_up_is_booked_only_with_the_same_patients_visit(session, clinics):
    clinic = clinics["a"]
    planned = follow_up(session, clinic, visit(session, clinic))
    elsewhere = book(session, clinics["b"])

    with pytest.raises(InvalidOutcomeError):
        mark_follow_up_booked(
            session, **who(clinic, "desk"), follow_up_id=planned.id, appointment_id=elsewhere.id
        )
    with pytest.raises(FollowUpNotFoundError):
        cancel_follow_up(session, **who(clinics["b"], "desk"), follow_up_id=planned.id)


# Referral


def test_a_clinician_writes_a_referral_and_line_breaks_are_kept(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    written = referral(session, clinic, encounter, specialty="  Cardiology ")

    assert written.reason == REASON
    assert written.specialty == "Cardiology"
    assert written.urgency == "urgent"
    assert written.status == "active"
    assert "referral.write" in actions(session, clinic)


@pytest.mark.parametrize(
    "changes",
    [{"to_name": "  "}, {"reason": "   "}, {"urgency": "whenever"}, {"reason": "x" * 2001}],
)
def test_incomplete_referrals_are_refused(session, clinics, changes):
    with pytest.raises(InvalidOutcomeError):
        referral(session, clinics["a"], visit(session, clinics["a"]), **changes)


def test_reading_a_referral_for_its_letter_is_logged(session, clinics):
    clinic = clinics["a"]
    written = referral(session, clinic, visit(session, clinic))

    found = get_referral(session, **who(clinic, "nurse"), referral_id=written.id)

    assert found.id == written.id
    assert "referral.view" in actions(session, clinic)
    with pytest.raises(ReferralNotFoundError):
        get_referral(session, **who(clinics["b"]), referral_id=written.id)


def test_only_the_writer_or_the_encounter_owner_cancels_a_referral(session, clinics):
    clinic = clinics["a"]
    encounter = visit(session, clinic)  # opened by the doctor
    by_nurse = referral(session, clinic, encounter, person="nurse")

    cancelled = cancel_referral(session, **who(clinic), referral_id=by_nurse.id)  # the owner

    assert cancelled.status == "cancelled"
    with pytest.raises(OutcomeMoveError):
        cancel_referral(session, **who(clinic, "nurse"), referral_id=by_nurse.id)
    other = referral(session, clinic, encounter)  # by the doctor
    with pytest.raises(NotReferralAuthorError):
        cancel_referral(session, **who(clinic, "nurse"), referral_id=other.id)


def test_follow_up_and_referral_through_the_api(session, run_id, clinics):
    client = TestClient(app)
    clinic = clinics["a"]
    encounter = visit(session, clinic)

    def bearer(role):
        token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    base = f"/api/v1/encounters/{encounter.id}"
    planned = client.post(
        f"{base}/follow-ups",
        json={"due_date": IN_TWO_WEEKS.isoformat(), "instructions": "Repeat BP."},
        headers=bearer("doctor"),
    )
    by_desk = client.post(
        f"{base}/follow-ups", json={"due_date": IN_TWO_WEEKS.isoformat()}, headers=bearer("front_desk")
    )
    due = client.get(
        "/api/v1/follow-ups/due",
        params={"until": IN_TWO_WEEKS.isoformat()},
        headers=bearer("front_desk"),
    )
    written = client.post(
        f"{base}/referrals",
        json={"to_name": "LUTH Cardiology clinic", "reason": REASON},
        headers=bearer("doctor"),
    )
    desk_reads = client.get(f"/api/v1/referrals/{written.json()['id']}", headers=bearer("front_desk"))

    assert planned.status_code == 201
    assert by_desk.status_code == 403
    assert due.status_code == 200
    assert due.json()[0]["patient_name"] == "Test Patient A"
    assert "instructions" not in due.json()[0]  # clinical: not for front desk
    assert "Repeat BP" not in due.text
    assert written.status_code == 201
    assert written.json()["urgency"] == "routine"
    assert desk_reads.status_code == 403
