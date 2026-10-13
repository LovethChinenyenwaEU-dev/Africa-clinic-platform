from datetime import timedelta

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.notifications.models import Reminder
from app.modules.notifications.service import reminder_due_at
from app.modules.scheduling.lifecycle import cancel_appointment, reschedule_appointment
from tests.scheduling_helpers import NOW, START, book, build_clinic, walk_in

IN_THREE_DAYS = NOW + timedelta(days=3)


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "rs")


def reminders(session, clinic):
    return session.exec(tenant_select(Reminder, clinic["tenant"].id)).all()


def test_reminder_is_due_24_hours_before_the_visit():
    assert reminder_due_at(IN_THREE_DAYS, NOW) == IN_THREE_DAYS - timedelta(hours=24)


def test_a_visit_sooner_than_24_hours_is_reminded_right_away():
    assert reminder_due_at(START, NOW) == NOW


def test_booking_a_visit_queues_one_pending_sms_reminder(session, clinic):
    appointment = book(session, clinic, starts_at=IN_THREE_DAYS)

    (reminder,) = reminders(session, clinic)

    assert reminder.appointment_id == appointment.id
    assert reminder.channel == "sms"
    assert reminder.status == "pending"
    assert reminder.due_at == IN_THREE_DAYS - timedelta(hours=24)


def test_a_walk_in_gets_no_reminder_because_they_are_already_here(session, clinic):
    walk_in(session, clinic)

    assert reminders(session, clinic) == []


def test_cancelling_a_visit_cancels_its_waiting_reminder(session, clinic):
    appointment = book(session, clinic, starts_at=IN_THREE_DAYS)

    cancel_appointment(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["desk"].id,
        appointment_id=appointment.id,
        now=NOW,
    )

    (reminder,) = reminders(session, clinic)
    session.refresh(reminder)
    assert reminder.status == "cancelled"


def test_cancelling_never_rewrites_a_reminder_that_was_already_sent(session, clinic):
    appointment = book(session, clinic, starts_at=IN_THREE_DAYS)
    (reminder,) = reminders(session, clinic)
    reminder.status = "sent"
    session.add(reminder)
    session.commit()

    cancel_appointment(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["desk"].id,
        appointment_id=appointment.id,
        now=NOW,
    )

    session.refresh(reminder)
    assert reminder.status == "sent"


def test_rescheduling_moves_the_reminder_to_the_new_time(session, clinic):
    appointment = book(session, clinic, starts_at=IN_THREE_DAYS)
    new_start = IN_THREE_DAYS + timedelta(days=2)

    reschedule_appointment(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["desk"].id,
        appointment_id=appointment.id,
        starts_at=new_start,
        now=NOW,
    )

    (reminder,) = reminders(session, clinic)
    session.refresh(reminder)
    assert reminder.status == "pending"
    assert reminder.due_at == new_start - timedelta(hours=24)


def test_rescheduling_after_a_reminder_was_sent_queues_a_fresh_one(session, clinic):
    appointment = book(session, clinic, starts_at=IN_THREE_DAYS)
    (reminder,) = reminders(session, clinic)
    reminder.status = "sent"
    reminder.attempts = 1
    reminder.provider_message_id = "fake-old"
    reminder.sent_at = NOW
    session.add(reminder)
    session.commit()

    reschedule_appointment(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["desk"].id,
        appointment_id=appointment.id,
        starts_at=IN_THREE_DAYS + timedelta(days=2),
        now=NOW,
    )

    session.refresh(reminder)
    assert reminder.status == "pending"
    assert reminder.attempts == 0
    assert reminder.provider_message_id is None
    assert reminder.sent_at is None
