from datetime import date

from app.modules.consent.service import grant_consent, publish_consent_text
from app.modules.patients.service import create_patient


def patient_who_agreed_to_reminders(session, clinic, *, name, phone):
    """A fake patient who said yes to reminders. phone may be None."""
    who = {"tenant_id": clinic["tenant"].id, "actor_id": clinic["desk"].id}
    patient = create_patient(
        session,
        full_name=name,
        date_of_birth=date(1985, 1, 1),
        sex="male",
        phone=phone,
        **who,
    )
    publish_consent_text(
        session, purpose="reminders", body="I agree to receive appointment reminders.", **who
    )
    grant_consent(
        session, patient_id=patient.id, purpose="reminders", granted_by="patient", **who
    )
    return patient
