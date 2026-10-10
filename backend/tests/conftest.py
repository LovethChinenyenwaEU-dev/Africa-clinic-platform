import uuid

import pytest
from sqlmodel import Session, col, select

from app.core.db import engine
from app.modules.identity.models import Staff
from app.modules.tenancy.models import Branch, Tenant


@pytest.fixture
def run_id():
    """A unique label so each test only touches its own fake data."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def session(run_id):
    """A database conversation that cleans up this test's fake data afterwards."""
    with Session(engine) as session:
        yield session

        session.rollback()
        staff_query = select(Staff).where(col(Staff.email).endswith(f"@{run_id}.example.com"))
        for staff in session.exec(staff_query).all():
            session.delete(staff)
        session.commit()

        tenant_query = select(Tenant).where(col(Tenant.name).contains(run_id))
        tenants = session.exec(tenant_query).all()
        for tenant in tenants:
            branch_query = select(Branch).where(Branch.tenant_id == tenant.id)
            for branch in session.exec(branch_query).all():
                session.delete(branch)
        session.commit()
        for tenant in tenants:
            session.delete(tenant)
        session.commit()