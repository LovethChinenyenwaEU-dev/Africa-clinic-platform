import uuid

import pytest
from sqlmodel import Session, col, select

from app.core.db import engine
from app.modules.consent.models import Consent, ConsentText
from app.modules.identity.models import Staff
from app.modules.notifications.models import Reminder
from app.modules.patients.models import Patient
from app.modules.records.models import Encounter
from app.modules.scheduling.models import Appointment
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
        tenants = session.exec(select(Tenant).where(col(Tenant.name).contains(run_id))).all()
        tenant_ids = [tenant.id for tenant in tenants]

        if tenant_ids:
            # Order matters: each table points at the next, so we clear them one at a time.
            for model in (Reminder, Encounter, Appointment, Consent, ConsentText, Patient):
                rows = session.exec(select(model).where(col(model.tenant_id).in_(tenant_ids)))
                for row in rows.all():
                    session.delete(row)
                session.commit()

        staff_query = select(Staff).where(col(Staff.email).endswith(f"@{run_id}.example.com"))
        for staff in session.exec(staff_query).all():
            session.delete(staff)
        session.commit()

        for tenant in tenants:
            branch_query = select(Branch).where(Branch.tenant_id == tenant.id)
            for branch in session.exec(branch_query).all():
                session.delete(branch)
        session.commit()
        for tenant in tenants:
            session.delete(tenant)
        session.commit()