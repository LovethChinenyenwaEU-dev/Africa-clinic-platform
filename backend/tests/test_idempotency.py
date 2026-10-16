import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.main import app
from app.modules.idempotency.models import IdempotencyRecord
from app.modules.idempotency.service import purge_old_records, request_hash, should_remember
from app.modules.identity.service import login, set_staff_active
from tests.scheduling_helpers import PASSWORD, build_clinic, stored

WALK_INS = "/api/v1/appointments/walk-ins"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "idem")


def headers(session, run_id, role, key=None):
    token = login(session, email=f"idem-{role}@{run_id}.example.com", password=PASSWORD)
    result = {"Authorization": f"Bearer {token}"}
    if key is not None:
        result["Idempotency-Key"] = key
    return result


def walk_in_form(clinic):
    return {"patient_id": str(clinic["patient"].id), "branch_id": str(clinic["branch"].id)}


def test_the_same_write_sent_three_times_happens_once(client, session, run_id, clinic):
    """SRS acceptance test for FR-O3."""
    h = headers(session, run_id, "front_desk", key=str(uuid.uuid4()))

    answers = [client.post(WALK_INS, json=walk_in_form(clinic), headers=h) for _ in range(3)]

    assert [answer.status_code for answer in answers] == [201, 201, 201]
    assert answers[0].json() == answers[1].json() == answers[2].json()
    assert "idempotent-replayed" not in answers[0].headers
    assert answers[1].headers["idempotent-replayed"] == "true"
    assert len(stored(session, clinic)) == 1


def test_without_the_header_writes_behave_as_before(client, session, run_id, clinic):
    h = headers(session, run_id, "front_desk")

    client.post(WALK_INS, json=walk_in_form(clinic), headers=h)
    client.post(WALK_INS, json=walk_in_form(clinic), headers=h)

    assert len(stored(session, clinic)) == 2


def test_the_same_key_with_a_different_request_is_refused(client, session, run_id, clinic):
    key = str(uuid.uuid4())
    h = headers(session, run_id, "front_desk", key=key)
    client.post(WALK_INS, json=walk_in_form(clinic), headers=h)

    different = walk_in_form(clinic) | {"duration_minutes": 45}
    answer = client.post(WALK_INS, json=different, headers=h)

    assert answer.status_code == 422
    assert "different request" in answer.json()["detail"]
    assert len(stored(session, clinic)) == 1


def test_one_persons_key_never_replays_to_someone_else(client, session, run_id, clinic):
    key = str(uuid.uuid4())

    desk = headers(session, run_id, "front_desk", key)
    nurse = headers(session, run_id, "nurse", key)

    client.post(WALK_INS, json=walk_in_form(clinic), headers=desk)
    answer = client.post(WALK_INS, json=walk_in_form(clinic), headers=nurse)

    assert "idempotent-replayed" not in answer.headers  # it really ran, as the nurse
    assert len(stored(session, clinic)) == 2


def test_a_switched_off_person_gets_no_replay(client, session, run_id, clinic):
    key = str(uuid.uuid4())
    h = headers(session, run_id, "front_desk", key=key)
    client.post(WALK_INS, json=walk_in_form(clinic), headers=h)
    set_staff_active(
        session, tenant_id=clinic["tenant"].id, staff_id=clinic["desk"].id, active=False
    )

    answer = client.post(WALK_INS, json=walk_in_form(clinic), headers=h)

    assert answer.status_code == 401
    assert "idempotent-replayed" not in answer.headers


def test_a_request_refused_for_no_login_is_not_remembered(client, session, run_id, clinic):
    key = str(uuid.uuid4())
    refused = client.post(WALK_INS, json=walk_in_form(clinic), headers={"Idempotency-Key": key})

    accepted = client.post(
        WALK_INS, json=walk_in_form(clinic), headers=headers(session, run_id, "front_desk", key)
    )

    assert refused.status_code == 401
    assert accepted.status_code == 201
    assert "idempotent-replayed" not in accepted.headers


@pytest.mark.parametrize("bad_key", ["short", "has spaces in it", "x" * 101, "semi;colon-key"])
def test_a_malformed_key_is_refused_before_anything_runs(client, session, run_id, clinic, bad_key):
    answer = client.post(
        WALK_INS, json=walk_in_form(clinic), headers=headers(session, run_id, "front_desk", bad_key)
    )

    assert answer.status_code == 422
    assert stored(session, clinic) == []


def test_temporary_failures_are_never_remembered():
    assert should_remember(201) and should_remember(409) and should_remember(422)
    assert not any(should_remember(code) for code in (401, 408, 429, 500, 502, 503))


def test_the_fingerprint_changes_when_any_part_of_the_request_does():
    base = request_hash("POST", "/a", "", b"{}")

    assert base == request_hash("POST", "/a", "", b"{}")
    assert base != request_hash("POST", "/b", "", b"{}")
    assert base != request_hash("POST", "/a", "x=1", b"{}")
    assert base != request_hash("POST", "/a", "", b'{"a":1}')
    # Parts never blur together: "/a" + "b" is not "/ab" + "".
    assert request_hash("POST", "/a", "b", b"") != request_hash("POST", "/ab", "", b"")


def test_remembered_answers_are_deleted_after_a_day(client, session, run_id, clinic):
    key = str(uuid.uuid4())
    h = headers(session, run_id, "front_desk", key)
    client.post(WALK_INS, json=walk_in_form(clinic), headers=h)
    mine = select(IdempotencyRecord).where(col(IdempotencyRecord.key) == key)
    (record,) = session.exec(mine).all()

    purge_old_records(session, now=record.created_at + timedelta(hours=23))
    assert len(session.exec(mine).all()) == 1

    purge_old_records(session, now=record.created_at + timedelta(hours=25))
    assert session.exec(mine).all() == []
