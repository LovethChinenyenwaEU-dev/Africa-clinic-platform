"""Week 8 Step 4: entries taken offline before sign-off are accepted after it, marked late."""
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_scope import tenant_select
from app.main import app
from app.modules.identity.service import login
from app.modules.records.models import ClinicalNote, VitalSigns
from app.modules.records.notes import InvalidNoteError, list_encounter_notes, write_note
from app.modules.records.service import (
    EncounterNotOpenError,
    close_encounter,
    mark_entered_in_error,
    open_encounter,
)
from app.modules.records.vitals import VitalReadings, list_encounter_vitals, record_vitals
from tests.scheduling_helpers import PASSWORD, build_clinic

FEVER = VitalReadings(temperature_c=Decimal("38.4"), pulse_bpm=104)


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


@pytest.fixture
def times():
    """Opened two hours ago, signed off one hour ago. The tablet was offline between."""
    now = datetime.now(UTC)
    return {
        "opened": now - timedelta(hours=2),
        "during": now - timedelta(minutes=90),
        "closed": now - timedelta(hours=1),
        "after": now - timedelta(minutes=30),
    }


def who(clinic, person="nurse"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def signed_off_visit(session, clinic, times):
    doctor = who(clinic, "doctor")
    encounter = open_encounter(
        session, **doctor, patient_id=clinic["patient"].id, now=times["opened"]
    )
    return close_encounter(session, **doctor, encounter_id=encounter.id, now=times["closed"])


def vitals(session, clinic, encounter, **extra):
    return record_vitals(
        session, **who(clinic), encounter_id=encounter.id, readings=FEVER, **extra
    )


def note(session, clinic, encounter, **extra):
    return write_note(
        session,
        **who(clinic, "doctor"),
        encounter_id=encounter.id,
        kind="history",
        body="Fever for 3 days.",
        **extra,
    )


# Vitals


def test_vitals_taken_before_sign_off_are_accepted_and_marked_late(session, clinics, times):
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)

    late = vitals(session, clinic, encounter, measured_at=times["during"])

    assert late.synced_late is True
    assert late.measured_at == times["during"]
    shown = list_encounter_vitals(session, **who(clinic), encounter_id=encounter.id)
    assert [row.id for row in shown] == [late.id]


def test_vitals_on_time_are_not_marked_late(session, clinics):
    clinic = clinics["a"]
    encounter = open_encounter(session, **who(clinic, "doctor"), patient_id=clinic["patient"].id)

    on_time = vitals(session, clinic, encounter)

    assert on_time.synced_late is False


@pytest.mark.parametrize(
    "moment",
    [
        None,  # no device time: made now, after sign-off
        "after",  # dated after sign-off
        "before_opening",  # dated before the encounter began
    ],
)
def test_vitals_not_taken_during_the_encounter_are_refused(session, clinics, times, moment):
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)
    extra = {}
    if moment == "after":
        extra["measured_at"] = times["after"]
    elif moment == "before_opening":
        extra["measured_at"] = times["opened"] - timedelta(hours=1)

    with pytest.raises(EncounterNotOpenError):
        vitals(session, clinic, encounter, **extra)
    assert session.exec(tenant_select(VitalSigns, clinic["tenant"].id)).all() == []


def test_a_mistaken_encounter_takes_no_late_vitals(session, clinics, times):
    clinic = clinics["a"]
    doctor = who(clinic, "doctor")
    encounter = open_encounter(
        session, **doctor, patient_id=clinic["patient"].id, now=times["opened"]
    )
    mark_entered_in_error(session, **doctor, encounter_id=encounter.id, now=times["closed"])

    with pytest.raises(EncounterNotOpenError):
        vitals(session, clinic, encounter, measured_at=times["during"])


def test_a_late_set_sent_twice_is_saved_once(session, clinics, times):
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)
    device_id = uuid.uuid4()

    first = vitals(session, clinic, encounter, measured_at=times["during"], vitals_id=device_id)
    again = vitals(session, clinic, encounter, measured_at=times["during"], vitals_id=device_id)

    assert first.id == again.id == device_id
    assert len(session.exec(tenant_select(VitalSigns, clinic["tenant"].id)).all()) == 1


# Notes


def test_a_note_written_before_sign_off_is_accepted_and_marked_late(session, clinics, times):
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)

    late = note(session, clinic, encounter, written_at=times["during"])

    assert late.synced_late is True
    assert late.written_at == times["during"]
    assert late.recorded_at > times["closed"]  # when it reached the server
    shown = list_encounter_notes(session, **who(clinic, "doctor"), encounter_id=encounter.id)
    assert [row.id for row in shown] == [late.id]


def test_a_note_on_time_keeps_its_arrival_as_its_written_time(session, clinics):
    clinic = clinics["a"]
    encounter = open_encounter(session, **who(clinic, "doctor"), patient_id=clinic["patient"].id)

    on_time = note(session, clinic, encounter)

    assert on_time.synced_late is False
    assert on_time.written_at == on_time.recorded_at


def test_a_note_written_after_sign_off_is_refused(session, clinics, times):
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)

    for extra in ({}, {"written_at": times["after"]}):
        with pytest.raises(EncounterNotOpenError):
            note(session, clinic, encounter, **extra)
    assert session.exec(tenant_select(ClinicalNote, clinic["tenant"].id)).all() == []


@pytest.mark.parametrize(
    "written_at",
    [
        datetime(2026, 10, 16, 9, 0),  # no time zone
        datetime.now(UTC) + timedelta(hours=1),  # in the future
    ],
)
def test_a_note_time_must_be_real(session, clinics, written_at):
    clinic = clinics["a"]
    encounter = open_encounter(session, **who(clinic, "doctor"), patient_id=clinic["patient"].id)

    with pytest.raises(InvalidNoteError):
        note(session, clinic, encounter, written_at=written_at)


# Through the API


def test_a_late_note_through_the_api(session, run_id, clinics, times):
    client = TestClient(app)
    clinic = clinics["a"]
    encounter = signed_off_visit(session, clinic, times)
    token = login(session, email=f"a-doctor@{run_id}.example.com", password=PASSWORD)
    url = f"/api/v1/encounters/{encounter.id}/notes"
    headers = {"Authorization": f"Bearer {token}"}

    late = client.post(
        url,
        json={"kind": "history", "body": "x", "written_at": times["during"].isoformat()},
        headers=headers,
    )
    refused = client.post(url, json={"kind": "history", "body": "x"}, headers=headers)

    assert late.status_code == 201
    assert late.json()["synced_late"] is True
    assert refused.status_code == 409
