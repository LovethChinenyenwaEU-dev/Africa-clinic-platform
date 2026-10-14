"""Clearly fake demo data, so the app can be clicked through on a development machine.

Never for real use: it refuses to run unless ENVIRONMENT is development or test,
and every person it creates is called "Demo ..." with an example.com email.
"""
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session

from app.core.config import settings
from app.modules.consent.service import grant_consent, publish_consent_text
from app.modules.identity.models import Role
from app.modules.identity.service import EmailAlreadyUsedError, create_staff, email_is_taken
from app.modules.patients.service import create_patient
from app.modules.scheduling.service import book_appointment, register_walk_in
from app.modules.tenancy.service import create_branch
from app.provisioning import provision_clinic

ALLOWED_ENVIRONMENTS = ("development", "test")

# (role, name) for each demo login. Emails are <role>@<domain>.
STAFF = [
    (Role.FRONT_DESK.value, "Demo Desk Officer"),
    (Role.NURSE.value, "Demo Nurse Eze"),
    (Role.DOCTOR.value, "Demo Doctor Okafor"),
    (Role.BILLING.value, "Demo Billing Clerk"),
]

# Clearly fake patients: (name, date of birth, sex, phone).
PATIENTS = [
    ("Demo Patient Adaeze", date(1990, 5, 17), "female", "0803 000 0101"),
    ("Demo Patient Bayo", date(2025, 1, 10), "male", None),
    ("Demo Patient Chioma", date(1958, 11, 2), "female", "0803 000 0103"),
]

WORDING = {
    "treatment": "I agree to be examined and treated by the clinic's staff.",
    "reminders": "I agree that the clinic may send me appointment reminders by SMS or WhatsApp.",
}


class DemoNotAllowedError(Exception):
    """Demo data is only for development and test machines."""


@dataclass(frozen=True)
class DemoLogin:
    role: str
    email: str


def seed_demo(
    session: Session,
    *,
    password: str,
    clinic_name: str = "Demo Clinic",
    email_domain: str = "demo.example.com",
    now: datetime | None = None,
) -> list[DemoLogin]:
    """Create a demo clinic with staff, fake patients and a visit or two. Returns the logins."""
    if settings.environment not in ALLOWED_ENVIRONMENTS:
        raise DemoNotAllowedError(
            f"Demo data is only allowed when ENVIRONMENT is one of {ALLOWED_ENVIRONMENTS}."
        )
    emails = [f"admin@{email_domain}"] + [f"{role}@{email_domain}" for role, _ in STAFF]
    if any(email_is_taken(session, email) for email in emails):
        raise EmailAlreadyUsedError("The demo clinic already exists.")

    current = now or datetime.now(UTC)
    tenant, admin = provision_clinic(
        session,
        clinic_name=clinic_name,
        admin_name="Demo Admin",
        admin_email=emails[0],
        admin_password=password,
    )
    branch = create_branch(session, tenant_id=tenant.id, name="Main branch", city="Enugu")
    people = {
        role: create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{role}@{email_domain}",
            full_name=name,
            role=role,
            password=password,
        )
        for role, name in STAFF
    }
    desk = people[Role.FRONT_DESK.value]

    for purpose, body in WORDING.items():
        publish_consent_text(
            session, tenant_id=tenant.id, actor_id=admin.id, purpose=purpose, body=body
        )

    patients = [
        create_patient(
            session,
            tenant_id=tenant.id,
            actor_id=desk.id,
            full_name=name,
            date_of_birth=born,
            sex=sex,
            phone=phone,
        )
        for name, born, sex, phone in PATIENTS
    ]
    grant_consent(
        session,
        tenant_id=tenant.id,
        actor_id=desk.id,
        patient_id=patients[0].id,
        purpose="treatment",
        granted_by="patient",
    )

    # Someone already waiting, and someone booked for later, so the queue is not empty.
    register_walk_in(
        session,
        tenant_id=tenant.id,
        actor_id=desk.id,
        patient_id=patients[0].id,
        branch_id=branch.id,
        now=current,
    )
    book_appointment(
        session,
        tenant_id=tenant.id,
        actor_id=desk.id,
        patient_id=patients[2].id,
        branch_id=branch.id,
        clinician_id=people[Role.DOCTOR.value].id,
        starts_at=(current + timedelta(hours=2)).replace(second=0, microsecond=0),
        now=current,
    )

    return [DemoLogin(role="admin", email=emails[0])] + [
        DemoLogin(role=role, email=f"{role}@{email_domain}") for role, _ in STAFF
    ]
