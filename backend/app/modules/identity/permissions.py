from enum import StrEnum

from app.modules.identity.models import Role


class Capability(StrEnum):
    """One thing a person may be allowed to do."""

    BRANCH_READ = "branch:read"
    BRANCH_WRITE = "branch:write"
    STAFF_READ = "staff:read"
    STAFF_MANAGE = "staff:manage"


_EVERYONE = frozenset({Capability.BRANCH_READ})
_ADMIN_ONLY = frozenset(
    {Capability.BRANCH_WRITE, Capability.STAFF_READ, Capability.STAFF_MANAGE}
)

# The one table that says who may do what. Change a rule here, nowhere else.
ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ADMIN: _EVERYONE | _ADMIN_ONLY,
    Role.FRONT_DESK: _EVERYONE,
    Role.NURSE: _EVERYONE,
    Role.DOCTOR: _EVERYONE,
    Role.BILLING: _EVERYONE,
}


def capabilities_for(role: str) -> frozenset[Capability]:
    """Everything this role may do. Unknown or forgotten roles get nothing."""
    try:
        return ROLE_CAPABILITIES[Role(role)]
    except (ValueError, KeyError):
        return frozenset()


def role_has(role: str, capability: Capability) -> bool:
    return capability in capabilities_for(role)