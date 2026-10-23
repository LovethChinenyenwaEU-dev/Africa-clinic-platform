"""Week 9 Step 8a: patients sign in with a one-time SMS code and see their own visits
and approved summaries."""
import re
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import login
from app.modules.identity.tokens import (
    InvalidTokenError,
    create_patient_token,
    decode_access_token,
    decode_patient_token,
)
from app.modules.notifications.adapters import FakeAdapter
from app.modules.patients.service import create_patient
from app.modules.portal import signin
from app.modules.portal.signin import SignInFailedError, finish_sign_in, start_sign_in
from app.modules.records.service import close_encounter, open_encounter
from app.modules.records.summary import approve_summary, draft_summary
from tests.scheduling_helpers import NOW, PASSWORD, book, build_clinic

PHONE = "08031234567"
BORN = date(1990, 5, 17)  # build_clinic's patient


@pytest.fixture(autouse=True)
def not_development(monkeypatch):
    """Run as "test" wherever the tests run. The Codespace runs the API as "development",
    which shows the sign-in code on screen; CI runs as "test". The answer must not
    depend on where the tests happen to run."""
    monkeypatch.setattr(settings, "environment", "test")


@pytest.fixture
def sms(monkeypatch):
    fake = FakeAdapter()
    monkeypatch.setattr(signin, "sms_adapter", lambda: fake)
    return fake


@pytest.fixture
def clinics(session, run_id):
    data = {label: build_clinic(session, run_id, label) for label in ("a", "b")}
    for clinic in data.values():
        clinic["patient"].phone = "+2348031234567"
        session.add(clinic["patient"])
    session.commit()
    return data


def tenant(clinic):
    return clinic["tenant"].id


def code_in(sms) -> str:
    return re.search(r"\b(\d{6})\b", sms.sent[-1].body).group(1)


def start(session, clinic, phone=PHONE, born=BORN, **extra):
    return start_sign_in(
        session, tenant_id=tenant(clinic), phone=phone, date_of_birth=born, **extra
    )


def finish(session, clinic, code, phone=PHONE, born=BORN, **extra):
    return finish_sign_in(
        session, tenant_id=tenant(clinic), phone=phone, date_of_birth=born, code=code, **extra
    )


def test_the_right_details_and_code_sign_the_patient_in(session, clinics, sms):
    clinic = clinics["a"]

    start(session, clinic, phone="0803 123 4567")  # typed with spaces
    token = finish(session, clinic, code_in(sms))

    claims = decode_patient_token(token)
    assert claims.patient_id == clinic["patient"].id
    assert sms.sent[0].to == "+2348031234567"
    assert "Never share it" in sms.sent[0].body
    actions = [e.action for e in list_audit_events(session, tenant_id=tenant(clinic))]
    assert {"portal.code_sent", "portal.sign_in"} <= set(actions)


def test_no_code_is_sent_unless_phone_and_birth_date_match_one_patient(session, clinics, sms):
    clinic = clinics["a"]

    start(session, clinic, born=date(1991, 1, 1))  # wrong date of birth
    start(session, clinic, phone="08099999999")  # unknown phone
    start(session, clinic, phone="not a phone")

    assert sms.sent == []


def test_two_patients_on_one_phone_are_told_apart_by_birth_date(session, clinics, sms):
    clinic = clinics["a"]
    child = create_patient(
        session,
        tenant_id=tenant(clinic),
        actor_id=clinic["desk"].id,
        full_name="Test Child",
        date_of_birth=date(2018, 3, 1),
        sex="male",
        phone=PHONE,
        confirmed_not_duplicate=True,
    )

    start(session, clinic, born=date(2018, 3, 1))
    token = finish(session, clinic, code_in(sms), born=date(2018, 3, 1))

    assert decode_patient_token(token).patient_id == child.id


def test_a_code_works_once_only_in_time_and_not_after_five_wrong_tries(session, clinics, sms):
    clinic = clinics["a"]
    now = datetime.now(UTC)

    start(session, clinic, now=now)
    code = code_in(sms)
    finish(session, clinic, code, now=now)
    with pytest.raises(SignInFailedError):  # used already
        finish(session, clinic, code, now=now)

    start(session, clinic, now=now)
    with pytest.raises(SignInFailedError):  # expired
        finish(session, clinic, code_in(sms), now=now + timedelta(minutes=11))

    start(session, clinic, now=now + timedelta(minutes=1))
    good = code_in(sms)
    for _ in range(5):
        with pytest.raises(SignInFailedError):
            finish(session, clinic, "000000" if good != "000000" else "111111", now=now)
    with pytest.raises(SignInFailedError):  # worn out, even with the right code
        finish(session, clinic, good, now=now)


def test_at_most_three_codes_per_phone_in_fifteen_minutes(session, clinics, sms):
    clinic = clinics["a"]
    now = datetime.now(UTC)

    for minute in range(5):
        start(session, clinic, now=now + timedelta(minutes=minute))
    start(session, clinic, now=now + timedelta(minutes=16))  # the window has moved on

    assert len(sms.sent) == 4


def test_another_clinic_does_not_sign_in_this_patient(session, clinics, sms):
    start(session, clinics["a"])

    with pytest.raises(SignInFailedError):
        finish(session, clinics["b"], code_in(sms))


def test_the_code_is_shown_on_screen_only_in_development(session, clinics, sms, monkeypatch):
    assert start(session, clinics["a"]).development_code is None
    monkeypatch.setattr(settings, "environment", "development")
    assert start(session, clinics["a"]).development_code == code_in(sms)


def test_patient_and_staff_tokens_never_stand_in_for_each_other(session, clinics, run_id):
    clinic = clinics["a"]
    patient_token = create_patient_token(patient_id=clinic["patient"].id, tenant_id=tenant(clinic))
    staff_token = login(session, email=f"a-doctor@{run_id}.example.com", password=PASSWORD)

    with pytest.raises(InvalidTokenError):
        decode_access_token(patient_token)
    with pytest.raises(InvalidTokenError):
        decode_patient_token(staff_token)


def test_the_patient_pages_through_the_api(session, run_id, clinics, sms):
    client = TestClient(app)
    clinic = clinics["a"]
    doctor = {"tenant_id": tenant(clinic), "actor_id": clinic["doctor"].id}
    upcoming = book(session, clinic, now=NOW - timedelta(days=30))
    book(session, clinics["b"], now=NOW - timedelta(days=30))  # another clinic's
    # One visit with an approved summary, one with only a draft.
    approved_visit = open_encounter(session, **doctor, patient_id=clinic["patient"].id)
    approved = draft_summary(
        session, **doctor, encounter_id=approved_visit.id, body="Approved words."
    )
    close_encounter(session, **doctor, encounter_id=approved_visit.id)
    approve_summary(session, **doctor, summary_id=approved.id)
    draft_visit = open_encounter(session, **doctor, patient_id=clinic["patient"].id)
    draft_summary(session, **doctor, encounter_id=draft_visit.id, body="Draft words.")
    details = {"clinic_id": str(tenant(clinic)), "phone": PHONE, "date_of_birth": "1990-05-17"}

    started = client.post("/api/v1/patient-portal/sign-in/start", json=details)
    real = code_in(sms)
    not_it = f"{(int(real) + 1) % 1_000_000:06d}"
    wrong = client.post("/api/v1/patient-portal/sign-in/finish", json={**details, "code": not_it})
    finished = client.post("/api/v1/patient-portal/sign-in/finish", json={**details, "code": real})
    patient = {"Authorization": f"Bearer {finished.json()['access_token']}"}
    staff = {
        "Authorization": "Bearer "
        + login(session, email=f"a-doctor@{run_id}.example.com", password=PASSWORD)
    }
    me = client.get("/api/v1/patient-portal/me", headers=patient)
    visits = client.get("/api/v1/patient-portal/visits", headers=patient)
    summaries = client.get("/api/v1/patient-portal/summaries", headers=patient)
    staff_tries = client.get("/api/v1/patient-portal/me", headers=staff)
    patient_tries_staff_door = client.get(
        f"/api/v1/encounters/{approved_visit.id}", headers=patient
    )

    assert started.status_code == 200
    assert started.json()["development_code"] is None  # tests run as "test", not development
    assert wrong.status_code == 401  # and that wrong try still leaves four more
    assert finished.status_code == 200
    assert me.json() == {"full_name": "Test Patient A"}
    assert [v["appointment_id"] for v in visits.json()] == [str(upcoming.id)]
    assert visits.json()[0]["clinician_name"] == "Test doctor"
    assert [s["body"] for s in summaries.json()] == ["Approved words."]
    assert staff_tries.status_code == 401
    assert patient_tries_staff_door.status_code == 401
