import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import (
    ROLE_CAPABILITIES,
    Capability,
    capabilities_for,
    role_has,
)

NON_ADMIN_ROLES = [Role.FRONT_DESK, Role.NURSE, Role.DOCTOR, Role.BILLING]
ADMIN_ONLY = [Capability.BRANCH_WRITE, Capability.STAFF_READ, Capability.STAFF_MANAGE]


def test_every_role_has_an_entry_in_the_table():
    assert set(ROLE_CAPABILITIES) == set(Role)


@pytest.mark.parametrize("role", list(Role))
def test_everyone_can_read_branches(role):
    assert role_has(role.value, Capability.BRANCH_READ)


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
@pytest.mark.parametrize("capability", ADMIN_ONLY)
def test_non_admins_cannot_do_admin_things(role, capability):
    assert not role_has(role.value, capability)


@pytest.mark.parametrize("capability", ADMIN_ONLY)
def test_admin_can_do_admin_things(capability):
    assert role_has(Role.ADMIN.value, capability)


def test_unknown_role_gets_nothing():
    assert capabilities_for("wizard") == frozenset()


def test_role_missing_from_the_table_gets_nothing(monkeypatch):
    monkeypatch.delitem(ROLE_CAPABILITIES, Role.NURSE)
    assert role_has("nurse", Capability.BRANCH_READ) is False