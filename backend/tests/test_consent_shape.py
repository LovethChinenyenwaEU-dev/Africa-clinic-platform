from app.modules.audit.service import AuditAction
from app.modules.consent.models import Consent, ConsentPurpose, GrantedBy

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "patient_id",
    "purpose",
    "consent_text_id",
    "granted_by",
    "recorded_by_id",
    "recorded_via",  # staff or patient_portal (Week 9)
    "granted_at",
    "revoked_at",
    "revoked_by_id",
}


def test_consent_table_holds_only_ids_codes_and_times():
    """No names or free text here. If someone adds a column, they must stop and think."""
    assert set(Consent.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_the_agreed_purposes_and_granters():
    assert {p.value for p in ConsentPurpose} == {
        "treatment",
        "reminders",
        "teleconsult",
        "referral_sharing",
    }
    assert {g.value for g in GrantedBy} == {"patient", "caregiver"}


def test_consent_actions_exist_in_the_diary_vocabulary():
    assert {"consent.grant", "consent.revoke"} <= {action.value for action in AuditAction}