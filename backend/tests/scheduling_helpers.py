from datetime import date, timedelta

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff
from app.modules.patients.service import create_patient
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.service import book_appointment, register_walk_in
from app.modules.tenancy.service import create_branch, create_tenant
from tests.dates import MONDAY, utc

PASSWORD = "a-long-enough-password"
NOW = utc(MONDAY, 8)
START = NOW + timedelta(hours=1)  # 09:00 UTC


def build_clinic(session, run_id, label):
    """A fake clinic with a branch, a front desk person, a doctor, a nurse and one patient."""
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


def appointment_actions(session, clinic):
    """The appointment lines in this clinic's diary, as a sorted list of action names."""
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(event.action for event in events if event.action.startswith("appointment."))