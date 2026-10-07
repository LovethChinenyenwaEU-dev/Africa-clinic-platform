import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.db import engine
from app.modules.identity.models import Role, Staff
from app.modules.tenancy.models import Tenant


def test_staff_email_must_be_unique():
    """The database itself must refuse two staff with the same email."""
    email = f"nurse-{uuid.uuid4()}@example.com"

    with Session(engine) as session:
        tenant = Tenant(name=f"Test Clinic {uuid.uuid4()}")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

        first = Staff(
            tenant_id=tenant.id,
            email=email,
            full_name="Test Nurse",
            role=Role.NURSE.value,
            password_hash="not-a-real-hash",
        )
        session.add(first)
        session.commit()

        duplicate = Staff(
            tenant_id=tenant.id,
            email=email,
            full_name="Someone Else",
            role=Role.DOCTOR.value,
            password_hash="not-a-real-hash",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.delete(first)
        session.commit()
        session.delete(tenant)
        session.commit()