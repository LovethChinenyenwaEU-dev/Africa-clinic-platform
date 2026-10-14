from datetime import UTC, datetime

import pytest
from sqlmodel import col, select

from app.core.config import settings
from app.core.tenant_scope import tenant_select
from app.demo_data import DemoNotAllowedError, seed_demo
from app.modules.identity.service import EmailAlreadyUsedError, login
from app.modules.patients.models import Patient
from app.modules.scheduling.models import Appointment
from app.modules.tenancy.models import Tenant

PASSWORD = "a-long-enough-password"
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)


def seed(session, run_id):
    return seed_demo(
        session,
        password=PASSWORD,
        clinic_name=f"Demo {run_id}",
        email_domain=f"{run_id}.example.com",
        now=NOW,
    )


def demo_tenant(session, run_id):
    return session.exec(select(Tenant).where(col(Tenant.name) == f"Demo {run_id}")).one()


def test_every_demo_login_works_with_the_chosen_password(session, run_id):
    logins = seed(session, run_id)

    assert {entry.role for entry in logins} == {
        "admin",
        "front_desk",
        "nurse",
        "doctor",
        "billing",
    }
    for entry in logins:
        assert login(session, email=entry.email, password=PASSWORD)


def test_demo_patients_are_clearly_fake(session, run_id):
    seed(session, run_id)
    tenant = demo_tenant(session, run_id)

    patients = session.exec(tenant_select(Patient, tenant.id)).all()

    assert len(patients) == 3
    assert all(patient.full_name.startswith("Demo Patient") for patient in patients)


def test_the_queue_is_not_empty(session, run_id):
    seed(session, run_id)
    tenant = demo_tenant(session, run_id)

    visits = session.exec(tenant_select(Appointment, tenant.id)).all()

    assert sorted(visit.status for visit in visits) == ["booked", "waiting"]


def test_running_it_twice_creates_nothing_the_second_time(session, run_id):
    seed(session, run_id)

    with pytest.raises(EmailAlreadyUsedError):
        seed(session, run_id)
    assert len(session.exec(select(Tenant).where(col(Tenant.name).contains(run_id))).all()) == 1


@pytest.mark.parametrize("environment", ["production", "staging", "prod", ""])
def test_it_refuses_anywhere_but_development_and_test(session, run_id, monkeypatch, environment):
    monkeypatch.setattr(settings, "environment", environment)

    with pytest.raises(DemoNotAllowedError):
        seed(session, run_id)
    assert session.exec(select(Tenant).where(col(Tenant.name).contains(run_id))).all() == []
