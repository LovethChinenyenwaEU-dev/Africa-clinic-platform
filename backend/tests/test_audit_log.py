import uuid

import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.audit.service import AuditAction, add_audit_event, list_audit_events


@pytest.fixture
def ids():
    """Fake IDs for one test. Nothing here is a real person."""
    return {
        "clinic": uuid.uuid4(),
        "other_clinic": uuid.uuid4(),
        "staff": uuid.uuid4(),
        "patient": uuid.uuid4(),
    }


def test_event_is_saved_when_the_caller_commits(session, ids):
    add_audit_event(
        session,
        tenant_id=ids["clinic"],
        actor_id=ids["staff"],
        action=AuditAction.PATIENT_VIEW,
        patient_id=ids["patient"],
        purpose="treatment",
    )
    session.commit()

    events = list_audit_events(session, tenant_id=ids["clinic"])
    assert len(events) == 1
    assert events[0].action == "patient.view"
    assert events[0].actor_id == ids["staff"]
    assert events[0].patient_id == ids["patient"]
    assert events[0].purpose == "treatment"


def test_rolled_back_action_leaves_no_diary_line(session, ids):
    """If the action is undone, its diary line is undone with it."""
    add_audit_event(
        session,
        tenant_id=ids["clinic"],
        actor_id=ids["staff"],
        action=AuditAction.PATIENT_CREATE,
        patient_id=ids["patient"],
    )
    session.rollback()

    assert list_audit_events(session, tenant_id=ids["clinic"]) == []


def test_one_clinic_never_sees_another_clinics_diary(session, ids):
    add_audit_event(
        session,
        tenant_id=ids["clinic"],
        actor_id=ids["staff"],
        action=AuditAction.PATIENT_VIEW,
        patient_id=ids["patient"],
    )
    add_audit_event(
        session,
        tenant_id=ids["other_clinic"],
        actor_id=uuid.uuid4(),
        action=AuditAction.PATIENT_VIEW,
        patient_id=uuid.uuid4(),
    )
    session.commit()

    mine = list_audit_events(session, tenant_id=ids["clinic"])
    assert len(mine) == 1
    assert all(event.tenant_id == ids["clinic"] for event in mine)


def test_can_filter_the_diary_by_patient(session, ids):
    other_patient = uuid.uuid4()
    for patient_id in (ids["patient"], other_patient):
        add_audit_event(
            session,
            tenant_id=ids["clinic"],
            actor_id=ids["staff"],
            action=AuditAction.PATIENT_VIEW,
            patient_id=patient_id,
        )
    session.commit()

    only_one = list_audit_events(session, tenant_id=ids["clinic"], patient_id=other_patient)
    assert len(only_one) == 1
    assert only_one[0].patient_id == other_patient


def test_the_database_refuses_to_change_a_diary_line(session, ids):
    event = add_audit_event(
        session,
        tenant_id=ids["clinic"],
        actor_id=ids["staff"],
        action=AuditAction.PATIENT_VIEW,
    )
    session.commit()

    event.action = AuditAction.PATIENT_CREATE.value
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()

    assert list_audit_events(session, tenant_id=ids["clinic"])[0].action == "patient.view"


def test_the_database_refuses_to_delete_a_diary_line(session, ids):
    event = add_audit_event(
        session,
        tenant_id=ids["clinic"],
        actor_id=ids["staff"],
        action=AuditAction.PATIENT_VIEW,
    )
    session.commit()

    session.delete(event)
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()

    assert len(list_audit_events(session, tenant_id=ids["clinic"])) == 1