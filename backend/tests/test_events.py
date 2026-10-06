from app.core import events


def test_publish_reaches_subscribers_and_only_them():
    events.clear_handlers()
    received = []
    events.subscribe("appointment.booked", received.append)

    events.publish(events.Event(name="appointment.booked", tenant_id="t1", payload={"id": "a1"}))
    events.publish(events.Event(name="something.else", tenant_id="t1"))

    assert len(received) == 1
    assert received[0].payload == {"id": "a1"}
    events.clear_handlers()
