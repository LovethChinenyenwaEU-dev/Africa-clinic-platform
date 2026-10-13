import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE])
def test_doctors_and_nurses_can_run_consultations(role):
    assert role_has(role.value, Capability.APPOINTMENT_CONSULT)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.ADMIN, Role.BILLING])
def test_nobody_else_can_run_consultations(role):
    assert not role_has(role.value, Capability.APPOINTMENT_CONSULT)