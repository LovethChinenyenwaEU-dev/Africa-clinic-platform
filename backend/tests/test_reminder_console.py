"""Week 11 Step 7c: the notification console. What the reminder worker did, for admins."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.notifications.models import Reminder
from app.modules.scheduling.models import Appointment
from tests.dates import MONDAY, utc
from tests.scheduling_helpers import PASSWORD, build_clinic

URL = "/api/v1/notifications/reminders"
STAFF_ROLES = {"desk": "front_desk", "doctor": "doctor", "nurse": "nurse"}


def headers(session, run_id, label, person):
    if person in STAFF_ROLES:
        email = f"{label}-{STAFF_ROLES[person]}@{run_id}.example.com"
    else:
        email = f"note-{label}-{person}@{run_id}.example.com"
    return {"Authorization": f"Bearer {login(session, email=email, password=PASSWORD)}"}


def monday():
    return {"from_day": MONDAY.isoformat(), "to_day": MONDAY.isoformat()}


def visit(session, clinic, *, hour, status="booked"):
    """A visit on MONDAY, put straight in the table (no reminder made for it)."""
    starts = utc(MONDAY, hour)
    row = Appointment(
        tenant_id=clinic["tenant"].id,
        branch_id=clinic["branch"].id,
        patient_id=clinic["patient"].id,
        kind="scheduled",
        visit_type="in_person",
        status=status,
        starts_at=starts,
        ends_at=starts + timedelta(minutes=15),
    )
    session.add(row)
    session.commit()
    return row


def reminder(session, clinic, appointment, *, status, last_error=None, attempts=0):
    row = Reminder(
        tenant_id=clinic["tenant"].id,
        appointment_id=appointment.id,
        channel="sms",
        status=status,
        due_at=appointment.starts_at - timedelta(hours=2),
        attempts=attempts,
        last_error=last_error,
        sent_at=appointment.starts_at - timedelta(hours=2) if status == "sent" else None,
    )
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        clinic = build_clinic(session, run_id, label)
        for role in ("admin", "billing"):
            clinic[role] = create_staff(
                session,
                tenant_id=clinic["tenant"].id,
                email=f"note-{label}-{role}@{run_id}.example.com",
                full_name=f"Test {role}",
                role=role,
                password=PASSWORD,
            )
        data[label] = clinic
    return data


@pytest.fixture
def reminders(session, clinics):
    """Clinic A's Monday: one sent, two failed (no phone; provider said no), one cancelled
    because the visit was cancelled. Clinic B has a failed one too."""
    a = clinics["a"]
    rows = {
        "sent": reminder(session, a, visit(session, a, hour=10), status="sent", attempts=1),
        "no_phone": reminder(
            session, a, visit(session, a, hour=11), status="failed", last_error="no_phone"
        ),
        "rejected": reminder(
            session,
            a,
            visit(session, a, hour=12),
            status="failed",
            last_error="provider_rejected",
            attempts=1,
        ),
        "cancelled": reminder(
            session,
            a,
            visit(session, a, hour=13, status="cancelled"),
            status="cancelled",
            last_error="visit_not_upcoming",
        ),
    }
    b = clinics["b"]
    rows["other_clinic"] = reminder(
        session, b, visit(session, b, hour=10), status="failed", last_error="no_phone"
    )
    return rows


def test_admin_sees_what_the_worker_did(session, run_id, reminders):
    response = TestClient(app).get(
        URL, params=monday(), headers=headers(session, run_id, "a", "admin")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"pending": 0, "sent": 1, "failed": 2, "cancelled": 1}
    assert body["failures"] == {"no_phone": 1, "provider_rejected": 1, "visit_not_upcoming": 1}
    assert len(body["lines"]) == 4
    assert body["more"] is False
    assert str(reminders["other_clinic"].id) not in response.text


def test_no_patient_details_are_shown(session, run_id, clinics, reminders):
    response = TestClient(app).get(
        URL, params=monday(), headers=headers(session, run_id, "a", "admin")
    )

    assert "Test Patient" not in response.text
    assert str(clinics["a"]["patient"].id) not in response.text
    assert set(response.json()["lines"][0]) == {
        "id",
        "appointment_id",
        "channel",
        "status",
        "due_at",
        "attempts",
        "last_error",
        "sent_at",
        "visit_starts_at",
        "visit_type",
        "can_retry",
    }


def test_only_one_status_can_be_shown(session, run_id, reminders):
    body = (
        TestClient(app)
        .get(
            URL,
            params=monday() | {"reminder_status": "failed"},
            headers=headers(session, run_id, "a", "admin"),
        )
        .json()
    )

    assert {line["id"] for line in body["lines"]} == {
        str(reminders["no_phone"].id),
        str(reminders["rejected"].id),
    }
    assert body["counts"]["sent"] == 1  # the counts still cover everything


def test_failed_reminders_for_upcoming_visits_can_be_retried(session, run_id, reminders):
    admin = headers(session, run_id, "a", "admin")
    lines = TestClient(app).get(URL, params=monday(), headers=admin).json()["lines"]
    retryable = {line["id"] for line in lines if line["can_retry"]}
    assert retryable == {str(reminders["no_phone"].id), str(reminders["rejected"].id)}

    response = TestClient(app).post(f"{URL}/{reminders['rejected'].id}/retry", headers=admin)

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    session.refresh(reminders["rejected"])
    assert (reminders["rejected"].attempts, reminders["rejected"].last_error) == (0, None)


def test_a_retry_is_written_in_the_audit_log(session, run_id, clinics, reminders):
    admin = headers(session, run_id, "a", "admin")

    TestClient(app).post(f"{URL}/{reminders['no_phone'].id}/retry", headers=admin)

    events = list_audit_events(session, tenant_id=clinics["a"]["tenant"].id)
    retries = [e for e in events if e.action == "reminder.retry"]
    assert [(e.actor_id, e.entity_id) for e in retries] == [
        (clinics["a"]["admin"].id, reminders["no_phone"].id)
    ]


@pytest.mark.parametrize("which", ["sent", "cancelled"])
def test_only_failed_reminders_for_booked_visits_can_be_retried(
    session, run_id, reminders, which
):
    response = TestClient(app).post(
        f"{URL}/{reminders[which].id}/retry", headers=headers(session, run_id, "a", "admin")
    )

    assert response.status_code == 409


def test_a_failed_reminder_for_a_cancelled_visit_cannot_be_retried(
    session, run_id, clinics, reminders
):
    a = clinics["a"]
    stale = reminder(
        session, a, visit(session, a, hour=14, status="cancelled"), status="failed"
    )

    response = TestClient(app).post(
        f"{URL}/{stale.id}/retry", headers=headers(session, run_id, "a", "admin")
    )

    assert response.status_code == 409
    assert "no longer booked" in response.json()["detail"]


def test_another_clinics_reminder_is_not_found(session, run_id, reminders):
    admin = headers(session, run_id, "a", "admin")

    other = TestClient(app).post(f"{URL}/{reminders['other_clinic'].id}/retry", headers=admin)
    unknown = TestClient(app).post(f"{URL}/{uuid.uuid4()}/retry", headers=admin)

    assert other.status_code == 404
    assert unknown.status_code == 404


def test_opening_it_is_written_in_the_audit_log(session, run_id, clinics, reminders):
    TestClient(app).get(URL, params=monday(), headers=headers(session, run_id, "a", "admin"))

    actions = [e.action for e in list_audit_events(session, tenant_id=clinics["a"]["tenant"].id)]
    assert "reminder.list" in actions


@pytest.mark.parametrize("person", ["billing", "desk", "nurse", "doctor"])
def test_only_admins_open_it(session, run_id, clinics, person):
    response = TestClient(app).get(URL, headers=headers(session, run_id, "a", person))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "params",
    [
        {"from_day": "2026-03-02", "to_day": "2026-03-01"},
        {"from_day": "2026-01-01", "to_day": "2026-03-01"},
        {"reminder_status": "lost"},
    ],
)
def test_bad_filters_are_refused(session, run_id, clinics, params):
    admin = headers(session, run_id, "a", "admin")

    response = TestClient(app).get(URL, params=params, headers=admin)

    assert response.status_code == 422
