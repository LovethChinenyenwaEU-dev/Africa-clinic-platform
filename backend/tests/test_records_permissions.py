import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has

CLINICAL = [Capability.CLINICAL_READ, Capability.CLINICAL_WRITE]


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE])
@pytest.mark.parametrize("capability", CLINICAL)
def test_doctors_and_nurses_can_use_the_clinical_record(role, capability):
    assert role_has(role.value, capability)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.ADMIN, Role.BILLING])
@pytest.mark.parametrize("capability", CLINICAL)
def test_nobody_else_can_read_or_write_the_clinical_record(role, capability):
    """Admins supervise through the diary, not by reading notes (ADR-0003)."""
    assert not role_has(role.value, capability)
