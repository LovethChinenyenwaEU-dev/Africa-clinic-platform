import uuid

from sqlmodel import Session, col, select

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.identity.models import Role, Staff
from app.modules.identity.passwords import check_password_rules, hash_password, verify_password
from app.modules.identity.tokens import create_access_token


class EmailAlreadyUsedError(Exception):
    """Raised when a staff member with this email already exists."""


class InvalidRoleError(ValueError):
    """Raised when the role is not one of the allowed job titles."""


class InvalidCredentialsError(Exception):
    """Wrong email or password, or the account is switched off."""


class StaffNotFoundError(Exception):
    """No staff member with this ID in this clinic."""


class LastAdminError(Exception):
    """Switching this person off would leave the clinic with no active admin."""


def normalise_email(email: str) -> str:
    """Remove stray spaces and capital letters so 'Ada@X.com' equals 'ada@x.com'."""
    return email.strip().lower()


def email_is_taken(session: Session, email: str) -> bool:
    """Say whether a staff member already uses this email."""
    clean_email = normalise_email(email)
    return session.exec(select(Staff).where(Staff.email == clean_email)).first() is not None


def create_staff(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    full_name: str,
    role: str,
    password: str,
) -> Staff:
    """Create a staff member the safe way. This is the only way staff get created."""
    check_password_rules(password)

    try:
        role_value = Role(role).value
    except ValueError:
        raise InvalidRoleError(f"Unknown role: {role}") from None

    if email_is_taken(session, email):
        raise EmailAlreadyUsedError("A staff member with this email already exists.")
    clean_email = normalise_email(email)

    staff = Staff(
        tenant_id=tenant_id,
        email=clean_email,
        full_name=full_name.strip(),
        role=role_value,
        password_hash=hash_password(password),
    )
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


def list_staff(session: Session, *, tenant_id: uuid.UUID) -> list[Staff]:
    """Every staff member of this clinic, and no other clinic's."""
    statement = tenant_select(Staff, tenant_id).order_by(col(Staff.full_name))
    return list(session.exec(statement).all())


def get_staff_in_tenant(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
) -> Staff | None:
    """One staff member, but only if they belong to this clinic."""
    row = get_in_tenant(session, Staff, tenant_id=tenant_id, row_id=staff_id)
    return row if isinstance(row, Staff) else None


def _active_admin_count(session: Session, tenant_id: uuid.UUID) -> int:
    statement = (
        tenant_select(Staff, tenant_id)
        .where(col(Staff.role) == Role.ADMIN.value)
        .where(col(Staff.is_active).is_(True))
    )
    return len(session.exec(statement).all())


def set_staff_active(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    active: bool,
) -> Staff:
    """Switch a staff member on or off. We switch people off; we never delete them."""
    staff = get_staff_in_tenant(session, tenant_id=tenant_id, staff_id=staff_id)
    if staff is None:
        raise StaffNotFoundError("Staff member not found.")

    switching_off_an_active_admin = (
        not active and staff.is_active and staff.role == Role.ADMIN.value
    )
    if switching_off_an_active_admin and _active_admin_count(session, tenant_id) <= 1:
        raise LastAdminError("A clinic must keep at least one active admin.")

    staff.is_active = active
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


# A smoothie of a throwaway password, used to keep timing the same.
_DUMMY_HASH = hash_password("a-password-nobody-uses")


def authenticate(session: Session, *, email: str, password: str) -> Staff:
    """Return the staff member if the email and password are right."""
    staff = session.exec(select(Staff).where(Staff.email == normalise_email(email))).first()

    if staff is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentialsError("Invalid email or password.")

    password_ok = verify_password(password, staff.password_hash)
    if not password_ok or not staff.is_active:
        raise InvalidCredentialsError("Invalid email or password.")
    return staff


def login(session: Session, *, email: str, password: str) -> str:
    """Check the password and hand back a wristband (access token)."""
    staff = authenticate(session, email=email, password=password)
    return create_access_token(
        staff_id=staff.id,
        tenant_id=staff.tenant_id,
        role=staff.role,
    )