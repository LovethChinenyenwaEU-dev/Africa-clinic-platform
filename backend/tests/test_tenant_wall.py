"""Week 11 Step 2: row-level security, the database's own wall between clinics (brief D2)."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, col, select

from app.core.db import engine
from app.core.tenant_wall import behind_wall, raise_tenant_wall
from app.main import app
from app.modules.identity.service import login
from app.modules.patients.models import Patient
from tests.scheduling_helpers import PASSWORD, build_clinic

OUTSIDE_THE_WALL = {"staff", "audit_chain_head"}  # the same list as migration 0032


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def tenant(clinic):
    return clinic["tenant"].id


def patient_ids(session):
    """Every patient this session can see, with no clinic filter at all: the query
    a bug would write."""
    return set(session.exec(select(Patient.id)).all())


def test_every_clinic_table_has_the_wall(session):
    """A new table with a tenant_id must get the policy too (migration 0032 shows how)."""
    rows = session.execute(
        text(
            """
            SELECT c.table_name, cls.relrowsecurity,
                   EXISTS (SELECT 1 FROM pg_policies p
                           WHERE p.tablename = c.table_name AND p.policyname = 'tenant_wall')
            FROM information_schema.columns c
            JOIN pg_class cls ON cls.relname = c.table_name AND cls.relkind = 'r'
            WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'
            """
        )
    ).all()

    walled = {name for name, rls_on, has_policy in rows if rls_on and has_policy}
    missing = {name for name, *_ in rows} - walled - OUTSIDE_THE_WALL
    assert missing == set()
    assert {"patient", "encounter", "invoice", "payment", "audit_event"} <= walled


def test_behind_the_wall_a_forgotten_filter_finds_only_this_clinic(clinics):
    a, b = clinics["a"], clinics["b"]
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(a))

        seen = patient_ids(walled)

    assert a["patient"].id in seen
    assert b["patient"].id not in seen


def test_without_a_wall_the_system_sees_every_clinic(session, clinics):
    """Signing in, the webhook and the reminder worker run without a wall."""
    seen = patient_ids(session)

    assert {clinics["a"]["patient"].id, clinics["b"]["patient"].id} <= seen
    assert behind_wall(session) is None


def test_the_wall_holds_after_a_commit(clinics):
    a, b = clinics["a"], clinics["b"]
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(a))
        patient_ids(walled)
        walled.commit()  # a new transaction starts behind the wall again

        seen = patient_ids(walled)
        assert behind_wall(walled) == tenant(a)

    assert a["patient"].id in seen
    assert b["patient"].id not in seen


def test_nothing_can_be_written_into_another_clinic(clinics):
    a, b = clinics["a"], clinics["b"]
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(a))
        walled.add(
            Patient(
                tenant_id=tenant(b),
                full_name="Slipped In",
                date_of_birth=date(1990, 1, 1),
                sex="female",
                created_by_id=a["desk"].id,
            )
        )
        with pytest.raises(DBAPIError, match="row-level security"):
            walled.commit()
        walled.rollback()


def test_another_clinics_row_cannot_be_changed_by_id(session, clinics):
    a, b = clinics["a"], clinics["b"]
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(a))
        changed = walled.execute(
            text("UPDATE patient SET full_name = 'Renamed' WHERE id = :id"),
            {"id": b["patient"].id},
        )
        walled.commit()

    assert changed.rowcount == 0
    session.refresh(b["patient"])
    assert b["patient"].full_name != "Renamed"


def test_a_walled_session_runs_as_the_app_role(clinics):
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(clinics["a"]))
        role, clinic = walled.execute(
            text("SELECT current_user, current_setting('app.tenant_id', true)")
        ).one()

    assert role == "clinic_app"
    assert clinic == str(tenant(clinics["a"]))


def test_the_wall_ends_with_the_session(clinics):
    """A pooled connection never carries one clinic's wall into the next request."""
    with Session(engine) as walled:
        raise_tenant_wall(walled, tenant(clinics["a"]))
        walled.execute(text("SELECT 1"))
        walled.commit()
    with Session(engine) as fresh:
        role, clinic = fresh.execute(
            text("SELECT current_user, current_setting('app.tenant_id', true)")
        ).one()

    assert role != "clinic_app"
    assert clinic in (None, "")


def test_signed_in_requests_run_behind_the_wall(session, run_id, clinics):
    """Through the API: a staff member of clinic A asking for B's patient finds nothing."""
    client = TestClient(app)
    token = login(session, email=f"a-front_desk@{run_id}.example.com", password=PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    own = client.get(f"/api/v1/patients/{clinics['a']['patient'].id}", headers=headers)
    other = client.get(f"/api/v1/patients/{clinics['b']['patient'].id}", headers=headers)

    assert own.status_code == 200
    assert other.status_code == 404
    still_there = session.exec(
        select(Patient).where(col(Patient.id) == clinics["b"]["patient"].id)
    ).one()
    assert still_there.tenant_id == tenant(clinics["b"])


def test_an_unknown_clinic_sees_nothing(clinics):
    with Session(engine) as walled:
        raise_tenant_wall(walled, uuid.uuid4())

        assert patient_ids(walled) == set()
