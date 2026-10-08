import uuid

import pytest
from sqlmodel import Session, col, select

from app.core.db import engine
from app.modules.identity.models import Role, Staff
from app.modules.identity.passwords import WeakPasswordError, verify_password
from app.modules.identity.service import EmailAlreadyUsedError
from app.modules.tenancy.models import Tenant
from app.provisioning import provision_clinic

GOOD_PASSWORD = "a-long-enough-password"


@pytest.fixture
def run_id():
    """A unique label so each test only touches its own fake data."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def session(run_id):
    with Session(engine) as session:
        yield session

        session.rollback()
        staff_query = select(Staff).where(col(Staff.email).endswith(f"@{run_id}.example.com"))
        for staff in session.exec(staff_query).all():
            session.delete(staff)
        session.commit()
        tenant_query = select(Tenant).where(col(Tenant.name).contains(run_id))
        for tenant in session.exec(tenant_query).all():
            session.delete(tenant)
        session.commit()


def test_provision_creates_a_clinic_and_its_admin(session, run_id):
    tenant, admin = provision_clinic(
        session,
        clinic_name=f"Clinic {run_id}",
        admin_name="Ada Admin",
        admin_email=f"admin@{run_id}.example.com",
        admin_password=GOOD_PASSWORD,
    )
    assert admin.tenant_id == tenant.id
    assert admin.role == Role.ADMIN.value
    assert verify_password(GOOD_PASSWORD, admin.password_hash) is True


def test_taken_email_creates_no_second_clinic(session, run_id):
    email = f"admin@{run_id}.example.com"
    provision_clinic(
        session,
        clinic_name=f"First {run_id}",
        admin_name="First Admin",
        admin_email=email,
        admin_password=GOOD_PASSWORD,
    )
    with pytest.raises(EmailAlreadyUsedError):
        provision_clinic(
            session,
            clinic_name=f"Second {run_id}",
            admin_name="Second Admin",
            admin_email=email,
            admin_password=GOOD_PASSWORD,
        )
    second = session.exec(select(Tenant).where(Tenant.name == f"Second {run_id}")).first()
    assert second is None


def test_weak_password_creates_no_clinic(session, run_id):
    with pytest.raises(WeakPasswordError):
        provision_clinic(
            session,
            clinic_name=f"Weak {run_id}",
            admin_name="Weak Admin",
            admin_email=f"admin@{run_id}.example.com",
            admin_password="short",
        )
    clinic = session.exec(select(Tenant).where(Tenant.name == f"Weak {run_id}")).first()
    assert clinic is None


def test_blank_clinic_name_creates_no_admin(session, run_id):
    email = f"admin@{run_id}.example.com"
    with pytest.raises(ValueError):
        provision_clinic(
            session,
            clinic_name="   ",
            admin_name="Nameless Admin",
            admin_email=email,
            admin_password=GOOD_PASSWORD,
        )
    admin = session.exec(select(Staff).where(Staff.email == email)).first()
    assert admin is None