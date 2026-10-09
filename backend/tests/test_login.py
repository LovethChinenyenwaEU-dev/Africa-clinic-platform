import uuid

import pytest
from sqlmodel import Session, col, select

from app.core.db import engine
from app.modules.identity.models import Staff
from app.modules.identity.service import InvalidCredentialsError, create_staff, login
from app.modules.identity.tokens import decode_access_token
from app.modules.tenancy.models import Tenant
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"


@pytest.fixture
def run_id():
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


@pytest.fixture
def account(session, run_id):
    tenant = create_tenant(session, name=f"Clinic {run_id}")
    return create_staff(
        session,
        tenant_id=tenant.id,
        email=f"nurse@{run_id}.example.com",
        full_name="Test Nurse",
        role="nurse",
        password=PASSWORD,
    )


def test_login_gives_a_token_with_the_right_identity(session, run_id, account):
    token = login(session, email=f"nurse@{run_id}.example.com", password=PASSWORD)
    claims = decode_access_token(token)
    assert claims.staff_id == account.id
    assert claims.tenant_id == account.tenant_id
    assert claims.role == "nurse"


def test_login_ignores_capitals_and_stray_spaces_in_the_email(session, run_id, account):
    token = login(session, email=f"  NURSE@{run_id}.EXAMPLE.COM ", password=PASSWORD)
    assert decode_access_token(token).staff_id == account.id


def test_wrong_password_and_unknown_email_look_identical(session, run_id, account):
    with pytest.raises(InvalidCredentialsError) as wrong_password:
        login(session, email=f"nurse@{run_id}.example.com", password="not-the-password")
    with pytest.raises(InvalidCredentialsError) as unknown_email:
        login(session, email=f"nobody@{run_id}.example.com", password=PASSWORD)
    assert str(wrong_password.value) == str(unknown_email.value)


def test_switched_off_account_cannot_log_in(session, run_id, account):
    account.is_active = False
    session.add(account)
    session.commit()
    with pytest.raises(InvalidCredentialsError):
        login(session, email=f"nurse@{run_id}.example.com", password=PASSWORD)