import pytest

from app.modules.identity.models import Role
from app.modules.identity.permissions import Capability, role_has

FRONT_LINE = [Role.FRONT_DESK, Role.NURSE, Role.DOCTOR]


@pytest.mark.parametrize("role", FRONT_LINE)
@pytest.mark.parametrize(
    "capability",
    [Capability.CONSENT_TEXT_READ, Capability.CONSENT_READ, Capability.CONSENT_WRITE],
)
def test_front_line_can_read_wording_and_record_consent(role, capability):
    assert role_has(role.value, capability)


@pytest.mark.parametrize("role", [*FRONT_LINE, Role.BILLING])
def test_only_admins_can_write_wording(role):
    assert not role_has(role.value, Capability.CONSENT_TEXT_WRITE)


def test_admin_manages_wording_but_has_no_patient_consent_access():
    assert role_has("admin", Capability.CONSENT_TEXT_WRITE)
    assert role_has("admin", Capability.CONSENT_TEXT_READ)
    assert not role_has("admin", Capability.CONSENT_READ)
    assert not role_has("admin", Capability.CONSENT_WRITE)


@pytest.mark.parametrize(
    "capability",
    [
        Capability.CONSENT_TEXT_READ,
        Capability.CONSENT_TEXT_WRITE,
        Capability.CONSENT_READ,
        Capability.CONSENT_WRITE,
    ],
)
def test_billing_has_no_consent_access(capability):
    assert not role_has("billing", capability)