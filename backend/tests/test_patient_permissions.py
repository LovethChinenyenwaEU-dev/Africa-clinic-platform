import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has

PATIENT_CAPABILITIES = [Capability.PATIENT_READ, Capability.PATIENT_WRITE]


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.NURSE, Role.DOCTOR])
@pytest.mark.parametrize("capability", PATIENT_CAPABILITIES)
def test_front_line_staff_can_read_and_register_patients(role, capability):
    assert role_has(role.value, capability)


def test_billing_can_read_but_not_register_patients():
    assert role_has("billing", Capability.PATIENT_READ)
    assert not role_has("billing", Capability.PATIENT_WRITE)


@pytest.mark.parametrize("capability", PATIENT_CAPABILITIES)
def test_admin_has_no_patient_access_by_default(capability):
    assert not role_has("admin", capability)