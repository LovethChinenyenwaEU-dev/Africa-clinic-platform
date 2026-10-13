import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has

APPOINTMENT_CAPABILITIES = [Capability.APPOINTMENT_READ, Capability.APPOINTMENT_WRITE]


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.NURSE, Role.DOCTOR])
@pytest.mark.parametrize("capability", APPOINTMENT_CAPABILITIES)
def test_front_line_staff_can_read_and_book_appointments(role, capability):
    assert role_has(role.value, capability)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.BILLING])
@pytest.mark.parametrize("capability", APPOINTMENT_CAPABILITIES)
def test_admin_and_billing_have_no_appointment_access(role, capability):
    assert not role_has(role.value, capability)