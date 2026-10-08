from sqlmodel import Session

from app.modules.identity.models import Role, Staff
from app.modules.identity.passwords import check_password_rules
from app.modules.identity.service import EmailAlreadyUsedError, create_staff, email_is_taken
from app.modules.tenancy.models import Tenant
from app.modules.tenancy.service import create_tenant


def provision_clinic(
    session: Session,
    *,
    clinic_name: str,
    admin_name: str,
    admin_email: str,
    admin_password: str,
) -> tuple[Tenant, Staff]:
    """Create a clinic and its first admin.

    Everything that can fail is checked before anything is saved, so we never
    leave behind a clinic that nobody can log into.
    """
    check_password_rules(admin_password)
    if email_is_taken(session, admin_email):
        raise EmailAlreadyUsedError("A staff member with this email already exists.")

    tenant = create_tenant(session, name=clinic_name)
    admin = create_staff(
        session,
        tenant_id=tenant.id,
        email=admin_email,
        full_name=admin_name,
        role=Role.ADMIN.value,
        password=admin_password,
    )
    return tenant, admin