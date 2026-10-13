from datetime import timedelta

import pytest
import redis

from app.core.config import settings
from app.core.tenant_scope import tenant_select
from app.modules.notifications.adapters import (
    FakeAdapter,
    NullAdapter,
    OutgoingMessage,
    UnknownProviderError,
    make_adapter,
)
from app.modules.notifications.models import Reminder
from app.worker import HEARTBEAT_KEY, run_once
from tests.notification_helpers import patient_who_agreed_to_reminders
from tests.scheduling_helpers import NOW, book, build_clinic

VISIT = NOW + timedelta(days=3)
SEND_TIME = VISIT - timedelta(hours=24)


@pytest.fixture
def redis_client():
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    client.delete(HEARTBEAT_KEY)


def test_provider_none_gives_the_adapter_that_sends_nothing():
    assert isinstance(make_adapter("none"), NullAdapter)


def test_an_unknown_provider_name_stops_the_worker_from_starting():
    with pytest.raises(UnknownProviderError):
        make_adapter("not-a-provider")


def test_the_null_adapter_accepts_messages_without_keeping_them():
    adapter = NullAdapter()
    receipt = adapter.send(OutgoingMessage(to="+2348030000001", body="Reminder"))
    assert receipt.provider_message_id.startswith("none-")
    assert not hasattr(adapter, "sent")


def test_one_tick_sends_due_reminders_and_records_a_heartbeat(session, run_id, redis_client):
    clinic = build_clinic(session, run_id, "w")
    patient = patient_who_agreed_to_reminders(
        session, clinic, name="Test Patient Worker", phone="0803 000 0002"
    )
    book(session, clinic, patient_id=patient.id, starts_at=VISIT)
    adapter = FakeAdapter()

    result = run_once(
        session, redis_client, adapter=adapter, now=SEND_TIME, tenant_id=clinic["tenant"].id
    )

    assert result.sent == 1
    assert len(adapter.sent) == 1
    (reminder,) = session.exec(tenant_select(Reminder, clinic["tenant"].id)).all()
    assert reminder.status == "sent"
    assert redis_client.get(HEARTBEAT_KEY) == SEND_TIME.isoformat()
