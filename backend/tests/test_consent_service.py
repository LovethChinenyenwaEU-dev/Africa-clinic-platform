from datetime import date

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.consent.models import Consent, ConsentText
from app.modules.consent.service import (
    ConsentNotFoundError,
    InvalidConsentError,
    NoConsentTextError,
    current_consent_text,
    grant_consent,
    has_active_consent,
    publish_consent_text,
    revoke_consent,
)
from app.modules.identity.service import create_staff
from app.modules.patients.service import PatientNotFoundError, create_patient
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"


@pytest.fixture
def clinics(session, run_id):
    """Two clinics, each with a front desk person and one patient. All fake."""
    data = {}
    for label in ("a", "b"):
        tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
        staff = create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{label}@{run_id}.example.com",
            full_name=f"Desk {label}",
            role="front_desk",
            password=PASSWORD,
        )
        patient = create_patient(
            session,
            tenant_id=tenant.id,
            actor_id=staff.id,
            full_name=f"Test Patient {label.upper()}",
            date_of_birth=date(1990, 5, 17),
            sex="female",
        )
        data[label] = {"tenant": tenant, "staff": staff, "patient": patient}
    return data


def who(clinic):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic["staff"].id}


def publish(session, clinic, purpose="treatment", body="I agree to treatment."):
    return publish_consent_text(session, purpose=purpose, body=body, **who(clinic))


def grant(session, clinic, purpose="treatment", granted_by="patient"):
    return grant_consent(
        session,
        patient_id=clinic["patient"].id,
        purpose=purpose,
        granted_by=granted_by,
        **who(clinic),
    )


def revoke(session, clinic, purpose="treatment"):
    return revoke_consent(
        session, patient_id=clinic["patient"].id, purpose=purpose, **who(clinic)
    )


def active(session, clinic, purpose="treatment"):
    return has_active_consent(
        session,
        tenant_id=clinic["tenant"].id,
        patient_id=clinic["patient"].id,
        purpose=purpose,
    )


def stored_consents(session, clinic):
    return session.exec(tenant_select(Consent, clinic["tenant"].id)).all()


def stored_texts(session, clinic):
    return session.exec(tenant_select(ConsentText, clinic["tenant"].id)).all()


def consent_actions(session, clinic):
    events = list_audit_events(
        session, tenant_id=clinic["tenant"].id, patient_id=clinic["patient"].id
    )
    return sorted(event.action for event in events if event.action.startswith("consent."))


def test_each_published_text_gets_the_next_version_and_old_ones_stay(session, clinics):
    clinic = clinics["a"]
    first = publish(session, clinic, body="First wording.")
    second = publish(session, clinic, body="Second wording.")

    assert (first.version, second.version) == (1, 2)
    current = current_consent_text(session, tenant_id=clinic["tenant"].id, purpose="treatment")
    assert current.id == second.id
    assert len(stored_texts(session, clinic)) == 2


def test_versions_are_separate_per_purpose_and_per_clinic(session, clinics):
    a, b = clinics["a"], clinics["b"]
    assert publish(session, a, purpose="treatment").version == 1
    assert publish(session, a, purpose="reminders").version == 1
    assert publish(session, b, purpose="treatment").version == 1
    assert current_consent_text(session, tenant_id=b["tenant"].id, purpose="reminders") is None


@pytest.mark.parametrize(
    "purpose,body",
    [("treatment", "   "), ("treatment", "x" * 5001), ("wizardry", "Some text.")],
)
def test_bad_consent_text_is_refused_and_nothing_is_saved(session, clinics, purpose, body):
    clinic = clinics["a"]
    with pytest.raises(InvalidConsentError):
        publish(session, clinic, purpose=purpose, body=body)
    assert stored_texts(session, clinic) == []


def test_cannot_record_consent_before_any_wording_is_published(session, clinics):
    clinic = clinics["a"]
    with pytest.raises(NoConsentTextError):
        grant(session, clinic)
    assert stored_consents(session, clinic) == []
    assert consent_actions(session, clinic) == []


def test_granting_records_the_exact_wording_and_a_diary_line(session, clinics):
    clinic = clinics["a"]
    text = publish(session, clinic)

    consent = grant(session, clinic, granted_by="caregiver")

    assert consent.consent_text_id == text.id
    assert consent.granted_by == "caregiver"
    assert consent.recorded_by_id == clinic["staff"].id
    assert consent.revoked_at is None
    assert active(session, clinic)
    assert consent_actions(session, clinic) == ["consent.grant"]
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    assert [e.purpose for e in events if e.action == "consent.grant"] == ["treatment"]


def test_newer_wording_does_not_rewrite_what_the_patient_agreed_to(session, clinics):
    clinic = clinics["a"]
    old = publish(session, clinic, body="Old wording.")
    consent = grant(session, clinic)

    publish(session, clinic, body="New wording.")

    session.refresh(consent)
    assert consent.consent_text_id == old.id
    assert active(session, clinic)


def test_granting_twice_changes_nothing(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)

    first = grant(session, clinic)
    second = grant(session, clinic)

    assert first.id == second.id
    assert len(stored_consents(session, clinic)) == 1
    assert consent_actions(session, clinic) == ["consent.grant"]


def test_revoking_keeps_the_record_and_stops_the_consent(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic)
    grant(session, clinic)

    revoked = revoke(session, clinic)

    assert revoked.revoked_at is not None
    assert revoked.revoked_by_id == clinic["staff"].id
    assert not active(session, clinic)
    assert len(stored_consents(session, clinic)) == 1
    assert consent_actions(session, clinic) == ["consent.grant", "consent.revoke"]
    with pytest.raises(ConsentNotFoundError):
        revoke(session, clinic)


def test_granting_again_after_revoking_is_a_new_record_with_the_newest_wording(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic, body="Old wording.")
    grant(session, clinic)
    revoke(session, clinic)
    newest = publish(session, clinic, body="New wording.")

    again = grant(session, clinic)

    assert again.consent_text_id == newest.id
    assert len(stored_consents(session, clinic)) == 2
    assert active(session, clinic)


def test_consent_is_per_purpose_and_per_patient(session, clinics):
    clinic = clinics["a"]
    publish(session, clinic, purpose="reminders")
    publish(session, clinic, purpose="teleconsult")
    grant(session, clinic, purpose="reminders")

    assert active(session, clinic, purpose="reminders")
    assert not active(session, clinic, purpose="teleconsult")

    other_patient = create_patient(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["staff"].id,
        full_name="Test Patient Other",
        date_of_birth=date(1985, 1, 1),
        sex="male",
    )
    assert not has_active_consent(
        session,
        tenant_id=clinic["tenant"].id,
        patient_id=other_patient.id,
        purpose="reminders",
    )


def test_another_clinics_patient_cannot_be_given_consent(session, clinics):
    a, b = clinics["a"], clinics["b"]
    publish(session, b)

    with pytest.raises(PatientNotFoundError):
        grant_consent(
            session,
            tenant_id=b["tenant"].id,
            actor_id=b["staff"].id,
            patient_id=a["patient"].id,
            purpose="treatment",
            granted_by="patient",
        )

    assert stored_consents(session, a) == []
    assert stored_consents(session, b) == []


def test_another_clinic_cannot_see_or_revoke_my_consent(session, clinics):
    a, b = clinics["a"], clinics["b"]
    publish(session, a)
    grant(session, a)

    assert not has_active_consent(
        session, tenant_id=b["tenant"].id, patient_id=a["patient"].id, purpose="treatment"
    )
    with pytest.raises(ConsentNotFoundError):
        revoke_consent(
            session,
            tenant_id=b["tenant"].id,
            actor_id=b["staff"].id,
            patient_id=a["patient"].id,
            purpose="treatment",
        )
    assert active(session, a)


@pytest.mark.parametrize("changes", [{"purpose": "wizardry"}, {"granted_by": "stranger"}])
def test_bad_consent_details_are_refused_and_nothing_is_saved(session, clinics, changes):
    clinic = clinics["a"]
    publish(session, clinic)

    with pytest.raises(InvalidConsentError):
        grant(session, clinic, **changes)

    assert stored_consents(session, clinic) == []
    assert consent_actions(session, clinic) == []