import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.modules.audit.models import AuditEvent
from app.modules.audit.service import InvalidAuditFilterError, list_audit_events, view_audit_log

MONDAY = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


@pytest.fixture
def diary(session):
    """Three fake diary lines in one fake clinic: two by a nurse, one by a doctor."""
    clinic, nurse, doctor = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    lines = [
        (nurse, MONDAY, "vitals.record"),
        (doctor, MONDAY + timedelta(days=1), "note.write"),
        (nurse, MONDAY + timedelta(days=2), "note.view"),
    ]
    for actor, moment, action in lines:
        session.add(
            AuditEvent(tenant_id=clinic, actor_id=actor, action=action, occurred_at=moment)
        )
    session.commit()
    return {"clinic": clinic, "nurse": nurse, "doctor": doctor}


def actions(events):
    return [event.action for event in events]


def test_filter_by_staff_member(session, diary):
    events = list_audit_events(session, tenant_id=diary["clinic"], staff_id=diary["nurse"])

    assert actions(events) == ["note.view", "vitals.record"]  # newest first


def test_since_is_inclusive_and_until_is_exclusive(session, diary):
    events = list_audit_events(
        session,
        tenant_id=diary["clinic"],
        since=MONDAY + timedelta(days=1),
        until=MONDAY + timedelta(days=2),
    )

    assert actions(events) == ["note.write"]


def test_filters_combine(session, diary):
    events = list_audit_events(
        session,
        tenant_id=diary["clinic"],
        staff_id=diary["nurse"],
        since=MONDAY + timedelta(hours=1),
    )

    assert actions(events) == ["note.view"]


def test_a_time_in_another_time_zone_means_the_same_moment(session, diary):
    lagos = MONDAY.astimezone(timezone(timedelta(hours=1)))  # 10:00 in Lagos is 09:00 UTC
    events = list_audit_events(
        session, tenant_id=diary["clinic"], since=lagos, until=lagos + timedelta(minutes=1)
    )

    assert actions(events) == ["vitals.record"]


@pytest.mark.parametrize(
    "since,until",
    [
        (datetime(2026, 10, 12, 9, 0), None),  # no time zone
        (None, datetime(2026, 10, 12, 9, 0)),
        (MONDAY, MONDAY),  # empty range
        (MONDAY + timedelta(days=1), MONDAY),  # backwards
    ],
)
def test_a_senseless_range_is_refused(session, diary, since, until):
    with pytest.raises(InvalidAuditFilterError):
        list_audit_events(session, tenant_id=diary["clinic"], since=since, until=until)


def test_a_refused_range_writes_no_diary_line(session, diary):
    admin = uuid.uuid4()

    with pytest.raises(InvalidAuditFilterError):
        view_audit_log(
            session, tenant_id=diary["clinic"], actor_id=admin, since=MONDAY, until=MONDAY
        )

    assert list_audit_events(session, tenant_id=diary["clinic"], staff_id=admin) == []
