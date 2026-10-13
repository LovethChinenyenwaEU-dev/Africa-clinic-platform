import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.tenant_scope import tenant_select
from app.modules.notifications.models import Reminder
from tests.scheduling_helpers import START, build_clinic, walk_in

DUE = START - timedelta(hours=24)


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "r")


def make_reminder(clinic, appointment, **changes):
    """Built by hand to test the table itself. Walk-ins are used because they get no
    automatic reminder, so the only reminders present are the ones a test adds."""
    values = {
        "tenant_id": clinic["tenant"].id,
        "appointment_id": appointment.id,
        "channel": "sms",
        "status": "pending",
        "due_at": DUE,
    }
    return Reminder(**(values | changes))


def stored(session, clinic):
    return session.exec(tenant_select(Reminder, clinic["tenant"].id)).all()


def test_reminder_roundtrip_starts_pending_with_no_attempts(session, clinic):
    appointment = walk_in(session, clinic)
    session.add(make_reminder(clinic, appointment))
    session.commit()

    (saved,) = stored(session, clinic)

    assert saved.due_at == DUE
    assert saved.status == "pending"
    assert saved.attempts == 0
    assert saved.last_error is None
    assert saved.provider_message_id is None
    assert saved.sent_at is None


def test_one_visit_cannot_get_two_reminders_on_the_same_channel(session, clinic):
    appointment = walk_in(session, clinic)
    session.add(make_reminder(clinic, appointment))
    session.commit()

    session.add(make_reminder(clinic, appointment))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_one_visit_can_have_one_reminder_per_channel(session, clinic):
    appointment = walk_in(session, clinic)
    session.add(make_reminder(clinic, appointment, channel="sms"))
    session.add(make_reminder(clinic, appointment, channel="whatsapp"))
    session.commit()

    assert {reminder.channel for reminder in stored(session, clinic)} == {"sms", "whatsapp"}


@pytest.mark.parametrize("missing", ["tenant_id", "appointment_id"])
def test_every_link_must_point_at_something_real(session, clinic, missing):
    appointment = walk_in(session, clinic)
    session.add(make_reminder(clinic, appointment, **{missing: uuid.uuid4()}))

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
