import uuid
from datetime import date, timedelta, timezone

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff, set_staff_active
from app.modules.patients.service import PatientNotFoundError, create_patient
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import (
    BranchNotFoundError,
    ClinicianNotFoundError,
    InvalidAppointmentError,
    SlotTakenError,
    book_appointment,
    register_walk_in,
)
from app.modules.tenancy.service import create_branch, create_tenant
from tests.dates import MONDAY, utc

PASSWORD = "a-long-enough-password"
NOW = utc(MONDAY, 8)
START = NOW + timedelta(hours=1)  # 09:00 UTC


def build_clinic(session, run_id, label):
    tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
    people = {}
    for role in ("front_desk", "doctor", "nurse"):
        people[role] = create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{label}-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
    return {
        "tenant": tenant,
        "branch": create_branch(session, tenant_id=tenant.id, name=f"Branch {label}"),
        "desk": people["front_desk"],
        "doctor": people["doctor"],
        "nurse": people["nurse"],
        "patient": create_patient(
            session,
            tenant_id=tenant.id,
            actor_id=people["front_desk"].id,
            full_name=f"Test Patient {label.upper()}",
            date_of_birth=date(1990, 5, 17),
            sex="female",
        ),
    }


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def book(session, clinic, **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "actor_id": clinic["desk"].id,
        "patient_id": clinic["patient"].id,
        "branch_id": clinic["branch"].id,
        "clinician_id": clinic["doctor"].id,
        "starts_at": START,
        "now": NOW,
    }
    return book_appointment(session, **(values | changes))


def walk_in(session, clinic, **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "actor_id": clinic["desk"].id,
        "patient_id": clinic["patient"].id,
        "branch_id": clinic["branch"].id,
        "now": NOW,
    }
    return register_walk_in(session, **(values | changes))


def stored(session, clinic):
    return session.exec(tenant_select(Appointment, clinic["tenant"].id)).all()


def create_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [event for event in events if event.action == "appointment.create"]


def test_booking_saves_the_visit_and_a_diary_line(session, clinics):
    clinic = clinics["a"]

    appointment = book(session, clinic)

    assert appointment.status == "booked"
    assert appointment.kind == "scheduled"
    assert appointment.visit_type == "in_person"
    assert appointment.starts_at == START
    assert appointment.ends_at == START + timedelta(minutes=30)
    assert appointment.created_by_id == clinic["desk"].id
    (line,) = create_lines(session, clinic)
    assert line.patient_id == clinic["patient"].id
    assert line.actor_id == clinic["desk"].id


def test_a_time_given_in_another_zone_is_stored_as_the_same_moment(session, clinics):
    ten_in_lagos = START.astimezone(timezone(timedelta(hours=1)))  # 10:00 in Lagos

    appointment = book(session, clinics["a"], starts_at=ten_in_lagos)

    assert appointment.starts_at == START


def test_a_teleconsult_can_be_booked(session, clinics):
    appointment = book(session, clinics["a"], visit_type="teleconsult")
    assert appointment.visit_type == "teleconsult"


@pytest.mark.parametrize(
    "changes",
    [
        {"starts_at": NOW - timedelta(minutes=1)},
        {"starts_at": NOW + timedelta(days=366)},
        {"starts_at": START.replace(tzinfo=None)},  # no time zone
        {"duration_minutes": 4},
        {"duration_minutes": 241},
        {"visit_type": "home_visit"},
    ],
)
def test_bad_bookings_are_refused_and_nothing_is_saved(session, clinics, changes):
    clinic = clinics["a"]

    with pytest.raises(InvalidAppointmentError):
        book(session, clinic, **changes)

    assert stored(session, clinic) == []
    assert create_lines(session, clinic) == []


def test_only_active_doctors_and_nurses_of_this_clinic_can_be_booked(session, clinics):
    a, b = clinics["a"], clinics["b"]

    for clinician_id in (a["desk"].id, b["doctor"].id, uuid.uuid4()):
        with pytest.raises(ClinicianNotFoundError):
            book(session, a, clinician_id=clinician_id)
    assert stored(session, a) == []

    assert book(session, a, clinician_id=a["nurse"].id).clinician_id == a["nurse"].id

    set_staff_active(session, tenant_id=a["tenant"].id, staff_id=a["nurse"].id, active=False)
    with pytest.raises(ClinicianNotFoundError):
        book(session, a, clinician_id=a["nurse"].id, starts_at=START + timedelta(hours=2))
    assert len(stored(session, a)) == 1


def test_another_clinics_patient_or_branch_is_refused(session, clinics):
    a, b = clinics["a"], clinics["b"]

    with pytest.raises(PatientNotFoundError):
        book(session, a, patient_id=b["patient"].id)
    with pytest.raises(BranchNotFoundError):
        book(session, a, branch_id=b["branch"].id)

    assert stored(session, a) == []
    assert stored(session, b) == []
    assert create_lines(session, a) == []


def test_a_clinician_cannot_be_double_booked(session, clinics):
    clinic = clinics["a"]
    book(session, clinic)

    for starts_at in (START, START + timedelta(minutes=15), START - timedelta(minutes=15)):
        with pytest.raises(SlotTakenError):
            book(session, clinic, starts_at=starts_at)

    assert len(stored(session, clinic)) == 1
    assert len(create_lines(session, clinic)) == 1


def test_back_to_back_and_different_clinicians_are_fine(session, clinics):
    clinic = clinics["a"]
    book(session, clinic)

    book(session, clinic, starts_at=START + timedelta(minutes=30))
    book(session, clinic, starts_at=START - timedelta(minutes=30))
    book(session, clinic, clinician_id=clinic["nurse"].id)

    assert len(stored(session, clinic)) == 4


def test_a_cancelled_appointment_frees_its_time(session, clinics):
    clinic = clinics["a"]
    first = book(session, clinic)
    first.status = "cancelled"
    session.add(first)
    session.commit()

    again = book(session, clinic)

    assert again.status == "booked"


def test_a_walk_in_joins_the_queue_as_waiting_with_a_diary_line(session, clinics):
    clinic = clinics["a"]

    arrival = walk_in(session, clinic)

    assert arrival.kind == "walk_in"
    assert arrival.status == "waiting"
    assert arrival.visit_type == "in_person"
    assert arrival.clinician_id is None
    assert arrival.starts_at == NOW
    assert arrival.checked_in_at == NOW
    assert arrival.ends_at == NOW + timedelta(minutes=30)
    (line,) = create_lines(session, clinic)
    assert line.patient_id == clinic["patient"].id


def test_a_walk_in_may_name_a_clinician_who_must_be_valid(session, clinics):
    a, b = clinics["a"], clinics["b"]

    assert walk_in(session, a, clinician_id=a["doctor"].id).clinician_id == a["doctor"].id

    with pytest.raises(ClinicianNotFoundError):
        walk_in(session, a, clinician_id=b["doctor"].id)
    assert len(stored(session, a)) == 1


def test_walk_ins_follow_the_same_clinic_walls(session, clinics):
    a, b = clinics["a"], clinics["b"]

    with pytest.raises(PatientNotFoundError):
        walk_in(session, a, patient_id=b["patient"].id)
    with pytest.raises(BranchNotFoundError):
        walk_in(session, a, branch_id=b["branch"].id)
    with pytest.raises(InvalidAppointmentError):
        walk_in(session, a, duration_minutes=1)

    assert stored(session, a) == []
    assert create_lines(session, a) == []