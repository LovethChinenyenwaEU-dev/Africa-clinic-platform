from datetime import timedelta

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import SYSTEM_ACTOR_ID, list_audit_events
from app.modules.consent.service import revoke_consent
from app.modules.notifications.adapters import FakeAdapter
from app.modules.notifications.models import Reminder
from app.modules.notifications.sender import MAX_ATTEMPTS, send_due_reminders
from tests.notification_helpers import patient_who_agreed_to_reminders
from tests.scheduling_helpers import NOW, book, build_clinic

VISIT = NOW + timedelta(days=3)
SEND_TIME = VISIT - timedelta(hours=24)  # exactly when the reminder falls due
PHONE = "+2348030000001"  # clearly fake


@pytest.fixture
def clinic(session, run_id):
    clinic = build_clinic(session, run_id, "s")
    clinic["reachable"] = patient_who_agreed_to_reminders(
        session, clinic, name="Test Patient Reachable", phone="0803 000 0001"
    )
    return clinic


def book_reachable(session, clinic):
    return book(session, clinic, patient_id=clinic["reachable"].id, starts_at=VISIT)


def run(session, clinic, adapter, now=SEND_TIME):
    return send_due_reminders(session, adapter=adapter, now=now, tenant_id=clinic["tenant"].id)


def the_reminder(session, clinic):
    (reminder,) = session.exec(tenant_select(Reminder, clinic["tenant"].id)).all()
    session.refresh(reminder)
    return reminder


def test_a_due_reminder_is_sent_to_the_patients_phone(session, clinic):
    book_reachable(session, clinic)
    adapter = FakeAdapter()

    result = run(session, clinic, adapter)

    assert result.sent == 1
    (message,) = adapter.sent
    assert message.to == PHONE
    assert "Test Patient" not in message.body
    reminder = the_reminder(session, clinic)
    assert reminder.status == "sent"
    assert reminder.attempts == 1
    assert reminder.sent_at == SEND_TIME
    assert reminder.provider_message_id.startswith("fake-")


def test_each_send_is_written_in_the_diary_as_the_system(session, clinic):
    appointment = book_reachable(session, clinic)

    run(session, clinic, FakeAdapter())

    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    (send,) = [event for event in events if event.action == "reminder.send"]
    assert send.actor_id == SYSTEM_ACTOR_ID
    assert send.patient_id == appointment.patient_id


def test_a_reminder_that_is_not_due_yet_is_left_alone(session, clinic):
    book_reachable(session, clinic)
    adapter = FakeAdapter()

    result = run(session, clinic, adapter, now=SEND_TIME - timedelta(minutes=1))

    assert result.sent == 0
    assert adapter.sent == []
    assert the_reminder(session, clinic).status == "pending"


def test_a_provider_hiccup_is_retried_a_minute_later(session, clinic):
    book_reachable(session, clinic)

    result = run(session, clinic, FakeAdapter(fail_times=1))

    assert result.retrying == 1
    reminder = the_reminder(session, clinic)
    assert reminder.status == "pending"
    assert reminder.attempts == 1
    assert reminder.last_error == "provider_unavailable"
    assert reminder.due_at == SEND_TIME + timedelta(minutes=1)


def test_a_retried_reminder_goes_out_once_the_provider_recovers(session, clinic):
    book_reachable(session, clinic)
    adapter = FakeAdapter(fail_times=1)
    run(session, clinic, adapter)

    run(session, clinic, adapter, now=SEND_TIME + timedelta(minutes=1))

    reminder = the_reminder(session, clinic)
    assert reminder.status == "sent"
    assert reminder.attempts == 2
    assert reminder.last_error is None
    assert len(adapter.sent) == 1


def test_it_gives_up_after_the_last_attempt(session, clinic):
    book_reachable(session, clinic)
    adapter = FakeAdapter(fail_times=MAX_ATTEMPTS)

    now = SEND_TIME
    for _ in range(MAX_ATTEMPTS):
        run(session, clinic, adapter, now=now)
        now = the_reminder(session, clinic).due_at

    reminder = the_reminder(session, clinic)
    assert reminder.status == "failed"
    assert reminder.attempts == MAX_ATTEMPTS
    assert adapter.sent == []


def test_a_rejected_message_is_not_retried(session, clinic):
    book_reachable(session, clinic)

    result = run(session, clinic, FakeAdapter(fail_times=1, retryable=False))

    assert result.failed == 1
    reminder = the_reminder(session, clinic)
    assert reminder.status == "failed"
    assert reminder.last_error == "provider_rejected"


def test_a_patient_without_a_phone_is_marked_failed_without_calling_the_provider(
    session, clinic
):
    no_phone = patient_who_agreed_to_reminders(
        session, clinic, name="Test Patient No Phone", phone=None
    )
    book(session, clinic, patient_id=no_phone.id, starts_at=VISIT)
    adapter = FakeAdapter()

    result = run(session, clinic, adapter)

    assert result.failed == 1
    assert adapter.sent == []
    assert the_reminder(session, clinic).last_error == "no_phone"


def test_a_patient_who_never_agreed_gets_no_reminder(session, clinic):
    book(session, clinic, starts_at=VISIT)  # the default patient never agreed to reminders
    adapter = FakeAdapter()

    result = run(session, clinic, adapter)

    assert result.cancelled == 1
    assert adapter.sent == []
    reminder = the_reminder(session, clinic)
    assert reminder.status == "cancelled"
    assert reminder.last_error == "no_consent"
    assert reminder.attempts == 0


def test_consent_taken_back_after_booking_is_respected(session, clinic):
    book_reachable(session, clinic)
    revoke_consent(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["desk"].id,
        patient_id=clinic["reachable"].id,
        purpose="reminders",
    )
    adapter = FakeAdapter()

    result = run(session, clinic, adapter)

    assert result.cancelled == 1
    assert adapter.sent == []
    assert the_reminder(session, clinic).last_error == "no_consent"


def test_a_visit_that_is_no_longer_booked_gets_no_reminder(session, clinic):
    appointment = book_reachable(session, clinic)
    appointment.status = "waiting"  # the patient already checked in
    session.add(appointment)
    session.commit()
    adapter = FakeAdapter()

    result = run(session, clinic, adapter)

    assert result.cancelled == 1
    assert adapter.sent == []
    assert the_reminder(session, clinic).status == "cancelled"


def test_a_run_for_one_clinic_never_touches_another(session, clinic, run_id):
    other = build_clinic(session, run_id, "s2")
    book(session, other, starts_at=VISIT)
    book_reachable(session, clinic)

    run(session, clinic, FakeAdapter())

    (untouched,) = session.exec(tenant_select(Reminder, other["tenant"].id)).all()
    assert untouched.status == "pending"
