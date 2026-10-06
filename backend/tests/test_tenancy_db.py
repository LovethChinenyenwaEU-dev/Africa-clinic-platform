import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import engine
from app.main import app
from app.modules.tenancy.models import Branch, Tenant


def test_readiness_reaches_database_and_redis():
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200


def test_tenant_and_branch_roundtrip():
    """Proves migrations created the tables. Fake data only."""
    with Session(engine) as session:
        tenant = Tenant(name=f"Test Clinic {uuid.uuid4()}")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

        branch = Branch(tenant_id=tenant.id, name="Main branch", city="Test City")
        session.add(branch)
        session.commit()

        found = session.exec(select(Branch).where(Branch.tenant_id == tenant.id)).all()
        assert len(found) == 1

        session.delete(branch)
        session.delete(tenant)
        session.commit()
