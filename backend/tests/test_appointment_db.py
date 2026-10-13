import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.tenant_scope import tenant_select
from app.modules.identity.service import create_staff
from app.modules.patients.service import create_patient
from app.modules.scheduling.models import Appointment
from app.modules.tenancy.service import create_branch, create_tenant

PASSWORD = "a-long-enough-password"
START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


@pytest.fixture
def clinic(session, run_id):
    tenant = create_tenant(session, name=f"Clinic {run_id}")
    branch = create_branch(session, tenant_id=tenant.id, name="Main branch")
    doctor = create_staff(
        session,
        tenant_id=tenant.id,
        email=f"doctor@{run_id}.example.com",
        full_name="Test Doctor",
        role="doctor",
        password=PASSWORD,
    )
    patient = create_patient(
        session,
        tenant_id=tenant.id,
        actor_id=doctor.id,
        full_name="Test Patient Alpha",
        date_of_birth=date(1990, 5, 17),
        sex="female",
    )
    return {"tenant": tenant, "branch": branch, "doctor": doctor, "patient": patient}


def make_appointment(clinic, **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "branch_id": clinic["branch"].id,
        "patient_id": clinic["patient"].id,
        "clinician_id": clinic["doctor"].id,
        "kind": "scheduled",
        "visit_type": "in_person",
        "status": "booked",
        "starts_at": START,
        "ends_at": START + timedelta(minutes=30),
        "created_by_id": clinic["doctor"].id,
    }
    return Appointment(**(values | changes))


def stored(session, clinic):
    return session.exec(tenant_select(Appointment, clinic["tenant"].id)).all()


def test_appointment_roundtrip_keeps_the_moment_in_time(session, clinic):
    session.add(make_appointment(clinic))
    session.commit()

    (saved,) = stored(session, clinic)

    assert saved.starts_at == START
    assert saved.ends_at == START + timedelta(minutes=30)
    assert saved.status == "booked"
    assert saved.checked_in_at is None
    assert saved.consult_started_at is None
    assert saved.completed_at is None


def test_a_walk_in_can_exist_without_a_clinician(session, clinic):
    session.add(make_appointment(clinic, kind="walk_in", status="waiting", clinician_id=None))
    session.commit()

    (saved,) = stored(session, clinic)

    assert saved.clinician_id is None
    assert saved.kind == "walk_in"


@pytest.mark.parametrize("missing", ["branch_id", "patient_id", "clinician_id", "tenant_id"])
def test_every_link_must_point_at_something_real(session, clinic, missing):
    session.add(make_appointment(clinic, **{missing: uuid.uuid4()}))

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()