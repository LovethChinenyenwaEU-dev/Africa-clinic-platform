from enum import StrEnum

from app.modules.identity.models import Role


class Capability(StrEnum):
    """One thing a person may be allowed to do."""

    BRANCH_READ = "branch:read"
    BRANCH_WRITE = "branch:write"
    STAFF_READ = "staff:read"
    STAFF_MANAGE = "staff:manage"
    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    CONSENT_TEXT_READ = "consent_text:read"
    CONSENT_TEXT_WRITE = "consent_text:write"
    CONSENT_READ = "consent:read"
    CONSENT_WRITE = "consent:write"
    AUDIT_READ = "audit:read"


_EVERYONE = frozenset({Capability.BRANCH_READ})
_ADMIN_ONLY = frozenset(
    {
        Capability.BRANCH_WRITE,
        Capability.STAFF_READ,
        Capability.STAFF_MANAGE,
        Capability.CONSENT_TEXT_WRITE,
        Capability.AUDIT_READ,
    }
)
_WORDING_READERS = frozenset({Capability.CONSENT_TEXT_READ})
_PATIENT_READERS = frozenset({Capability.PATIENT_READ})
_PATIENT_REGISTRARS = _PATIENT_READERS | {Capability.PATIENT_WRITE}
_CONSENT_RECORDERS = frozenset({Capability.CONSENT_READ, Capability.CONSENT_WRITE})
_FRONT_LINE = _EVERYONE | _PATIENT_REGISTRARS | _CONSENT_RECORDERS | _WORDING_READERS

# The one table that says who may do what. Change a rule here, nowhere else.
ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ADMIN: _EVERYONE | _ADMIN_ONLY | _WORDING_READERS,
    Role.FRONT_DESK: _FRONT_LINE,
    Role.NURSE: _FRONT_LINE,
    Role.DOCTOR: _FRONT_LINE,
    Role.BILLING: _EVERYONE | _PATIENT_READERS,
}


def capabilities_for(role: str) -> frozenset[Capability]:
    """Everything this role may do. Unknown or forgotten roles get nothing."""
    try:
        return ROLE_CAPABILITIES[Role(role)]
    except (ValueError, KeyError):
        return frozenset()


def role_has(role: str, capability: Capability) -> bool:
    return capability in capabilities_for(role)