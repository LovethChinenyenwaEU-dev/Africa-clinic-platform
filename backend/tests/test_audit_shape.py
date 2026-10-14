from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditAction

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "actor_id",
    "patient_id",
    "entity_id",
    "action",
    "purpose",
    "occurred_at",
}


def test_audit_table_holds_only_ids_codes_and_times():
    """If someone adds a name, phone or notes column, this fails and they must stop and think."""
    assert set(AuditEvent.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_action_codes_look_like_noun_dot_verb():
    for action in AuditAction:
        noun, dot, verb = action.value.partition(".")
        assert noun and dot == "." and verb