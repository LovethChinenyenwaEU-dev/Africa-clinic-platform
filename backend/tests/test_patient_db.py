import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.modules.identity.service import create_staff
from app.modules.patients.models import Patient, Sex
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"


@pytest.fixture
def clinic(session, run_id):
    tenant = create_tenant(session, name=f"Clinic {run_id}")
    staff = create_staff(
        session,
        tenant_id=tenant.id,
        email=f"desk@{run_id}.example.com",
        full_name="Test Front Desk",
        role="front_desk",
        password=PASSWORD,
    )
    return {"tenant": tenant, "staff": staff}


def test_patient_roundtrip_with_and_without_a_phone(session, clinic):
    with_phone = Patient(
        tenant_id=clinic["tenant"].id,
        full_name="Test Patient One",
        date_of_birth=date(1990, 5, 17),
        sex=Sex.FEMALE.value,
        phone="+2348031234567",
        created_by_id=clinic["staff"].id,
    )
    without_phone = Patient(
        tenant_id=clinic["tenant"].id,
        full_name="Test Patient Two",
        date_of_birth=date(2015, 1, 2),
        sex=Sex.MALE.value,
        created_by_id=clinic["staff"].id,
    )
    session.add(with_phone)
    session.add(without_phone)
    session.commit()

    found = session.exec(
        select(Patient).where(Patient.tenant_id == clinic["tenant"].id)
    ).all()
    assert {patient.full_name for patient in found} == {"Test Patient One", "Test Patient Two"}
    by_name = {patient.full_name: patient for patient in found}
    assert by_name["Test Patient One"].phone == "+2348031234567"
    assert by_name["Test Patient Two"].phone is None


def test_patient_must_belong_to_a_real_clinic(session, clinic):
    orphan = Patient(
        tenant_id=uuid.uuid4(),
        full_name="Test Orphan",
        date_of_birth=date(1980, 1, 1),
        sex=Sex.OTHER.value,
        created_by_id=clinic["staff"].id,
    )
    session.add(orphan)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()