import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has


def test_admin_can_read_the_diary():
    assert role_has("admin", Capability.AUDIT_READ)


@pytest.mark.parametrize("role", [role for role in Role if role is not Role.ADMIN])
def test_nobody_else_can_read_the_diary(role):
    assert not role_has(role.value, Capability.AUDIT_READ)