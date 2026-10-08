import uuid

import pytest
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.identity.models import Staff
from app.modules.identity.passwords import WeakPasswordError, verify_password
from app.modules.identity.service import (
    EmailAlreadyUsedError,
    InvalidRoleError,
    create_staff,
)
from app.modules.tenancy.models import Tenant

GOOD_PASSWORD = "a-long-enough-password"


@pytest.fixture
def session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def tenant(session):
    """A fake clinic for one test, removed afterwards."""
    tenant = Tenant(name=f"Test Clinic {uuid.uuid4()}")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    yield tenant

    session.rollback()
    for staff in session.exec(select(Staff).where(Staff.tenant_id == tenant.id)).all():
        session.delete(staff)
    session.commit()
    session.delete(tenant)
    session.commit()


def test_create_staff_stores_a_hash_and_tidies_the_email(session, tenant):
    staff = create_staff(
        session,
        tenant_id=tenant.id,
        email=f"  Nurse-{uuid.uuid4()}@Example.com ",
        full_name="  Ada Test ",
        role="nurse",
        password=GOOD_PASSWORD,
    )
    assert staff.email == staff.email.strip().lower()
    assert staff.full_name == "Ada Test"
    assert staff.password_hash != GOOD_PASSWORD
    assert verify_password(GOOD_PASSWORD, staff.password_hash) is True
    assert staff.is_active is True


def test_duplicate_email_is_rejected_even_with_different_capitals(session, tenant):
    email = f"same-{uuid.uuid4()}@example.com"
    create_staff(
        session,
        tenant_id=tenant.id,
        email=email,
        full_name="First",
        role="nurse",
        password=GOOD_PASSWORD,
    )
    with pytest.raises(EmailAlreadyUsedError):
        create_staff(
            session,
            tenant_id=tenant.id,
            email=email.upper(),
            full_name="Second",
            role="doctor",
            password=GOOD_PASSWORD,
        )


def test_unknown_role_is_rejected(session, tenant):
    with pytest.raises(InvalidRoleError):
        create_staff(
            session,
            tenant_id=tenant.id,
            email=f"x-{uuid.uuid4()}@example.com",
            full_name="Wizard",
            role="wizard",
            password=GOOD_PASSWORD,
        )


def test_weak_password_is_rejected(session, tenant):
    with pytest.raises(WeakPasswordError):
        create_staff(
            session,
            tenant_id=tenant.id,
            email=f"y-{uuid.uuid4()}@example.com",
            full_name="Weak",
            role="nurse",
            password="short",
        )