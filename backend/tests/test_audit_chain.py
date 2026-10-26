"""Week 11 Step 1: the audit log is tamper-evident (a hash chain per clinic, brief D3)."""
import re
import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import col, select

from app.main import app
from app.modules.audit.chain import GENESIS, check_audit_chain
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditAction, add_audit_event, list_audit_events
from app.modules.identity.service import create_staff, login
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def write(session, clinic, count):
    actor = uuid.uuid4()
    for _ in range(count):
        add_audit_event(session, tenant_id=clinic, actor_id=actor, action=AuditAction.PATIENT_VIEW)
    session.commit()


def chain(session, clinic):
    statement = (
        select(AuditEvent)
        .where(col(AuditEvent.tenant_id) == clinic)
        .order_by(col(AuditEvent.chain_seq))
    )
    return list(session.exec(statement).all())


@contextmanager
def owner_with_the_lock_off(session):
    """What someone with database-owner rights could do: switch the append-only
    trigger off, tamper, and switch it back on. Always switched back on."""
    session.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update_delete"))
    try:
        yield
    finally:
        session.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_no_update_delete"))
        session.commit()


def test_every_line_is_numbered_and_linked_per_clinic(session):
    clinic, other = uuid.uuid4(), uuid.uuid4()
    write(session, clinic, 3)
    write(session, other, 1)

    lines = chain(session, clinic)

    assert [line.chain_seq for line in lines] == [1, 2, 3]
    assert lines[0].prev_hash == GENESIS
    assert [line.prev_hash for line in lines[1:]] == [line.row_hash for line in lines[:-1]]
    assert all(HEX64.match(line.row_hash or "") for line in lines)
    assert [line.chain_seq for line in chain(session, other)] == [1]  # its own chain


def test_a_clean_chain_checks_out_and_gives_its_head(session):
    clinic = uuid.uuid4()
    write(session, clinic, 4)

    result = check_audit_chain(session, tenant_id=clinic)

    assert result.ok
    assert (result.lines_checked, result.broken_at, result.problem) == (4, None, None)
    assert result.head_seq == 4
    assert result.head_hash == chain(session, clinic)[-1].row_hash


def test_the_app_cannot_choose_the_chain_values(session):
    clinic = uuid.uuid4()
    write(session, clinic, 1)
    session.add(
        AuditEvent(
            tenant_id=clinic,
            actor_id=uuid.uuid4(),
            action="patient.view",
            chain_seq=99,
            prev_hash="forged",
            row_hash="forged",
        )
    )
    session.commit()

    second = chain(session, clinic)[1]
    assert second.chain_seq == 2
    assert second.prev_hash != "forged"
    assert check_audit_chain(session, tenant_id=clinic).ok


def test_a_changed_line_breaks_the_chain_where_it_was_changed(session):
    clinic = uuid.uuid4()
    write(session, clinic, 3)
    target = chain(session, clinic)[1].id

    with owner_with_the_lock_off(session):
        session.execute(
            text("UPDATE audit_event SET action = 'patient.search' WHERE id = :id"), {"id": target}
        )
        session.commit()

    result = check_audit_chain(session, tenant_id=clinic)
    assert not result.ok
    assert result.broken_at == 2
    assert result.problem is not None and "changed" in result.problem


def test_a_removed_line_breaks_the_chain(session):
    clinic = uuid.uuid4()
    write(session, clinic, 3)
    target = chain(session, clinic)[1].id

    with owner_with_the_lock_off(session):
        session.execute(text("DELETE FROM audit_event WHERE id = :id"), {"id": target})
        session.commit()

    result = check_audit_chain(session, tenant_id=clinic)
    assert not result.ok
    assert result.broken_at == 3  # the line after the gap
    assert result.problem is not None and "missing" in result.problem


def test_the_lock_is_still_on_for_everyone_else(session):
    clinic = uuid.uuid4()
    write(session, clinic, 1)

    with pytest.raises(Exception, match="cannot be changed or deleted"):
        session.execute(
            text("UPDATE audit_event SET action = 'x.y' WHERE tenant_id = :t"), {"t": clinic}
        )
    session.rollback()


# --- the door ---------------------------------------------------------------------


def test_admins_check_the_chain_and_the_check_is_logged(session, run_id):
    tenant = create_tenant(session, name=f"Chain clinic {run_id}")
    for role in ("admin", "front_desk"):
        create_staff(
            session,
            tenant_id=tenant.id,
            email=f"chain-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
    client = TestClient(app)

    def bearer(role):
        token = login(session, email=f"chain-{role}@{run_id}.example.com", password=PASSWORD)
        return {"Authorization": f"Bearer {token}"}

    refused = client.get("/api/v1/audit/chain", headers=bearer("front_desk"))
    checked = client.get("/api/v1/audit/chain", headers=bearer("admin"))

    assert refused.status_code == 403
    assert checked.status_code == 200
    assert checked.json()["ok"] is True
    assert HEX64.match(checked.json()["head_hash"])
    actions = [e.action for e in list_audit_events(session, tenant_id=tenant.id)]
    assert "audit.verify" in actions
