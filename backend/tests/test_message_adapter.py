import pytest

from app.modules.notifications.adapters import (
    FakeAdapter,
    MessageAdapter,
    OutgoingMessage,
    ProviderError,
)

MESSAGE = OutgoingMessage(to="+2348031234567", body="Reminder: visit tomorrow 9am.")


def test_fake_adapter_records_what_it_was_asked_to_send():
    adapter = FakeAdapter()
    receipt = adapter.send(MESSAGE)
    assert adapter.sent == [MESSAGE]
    assert receipt.provider_message_id.startswith("fake-")


def test_each_send_gets_its_own_provider_id():
    adapter = FakeAdapter()
    first = adapter.send(MESSAGE)
    second = adapter.send(MESSAGE)
    assert first.provider_message_id != second.provider_message_id


def test_fake_adapter_can_fail_a_set_number_of_times_then_recover():
    adapter: MessageAdapter = FakeAdapter(fail_times=2)
    for _ in range(2):
        with pytest.raises(ProviderError) as caught:
            adapter.send(MESSAGE)
        assert caught.value.retryable is True
    adapter.send(MESSAGE)
    assert adapter.sent == [MESSAGE]


def test_failures_can_be_marked_as_not_worth_retrying():
    adapter = FakeAdapter(fail_times=1, retryable=False)
    with pytest.raises(ProviderError) as caught:
        adapter.send(MESSAGE)
    assert caught.value.retryable is False


def test_a_failed_send_is_not_recorded_as_sent():
    adapter = FakeAdapter(fail_times=1)
    with pytest.raises(ProviderError):
        adapter.send(MESSAGE)
    assert adapter.sent == []
