import uuid

from sqlmodel import Session, select

from app.modules.identity.models import Role, Staff
from app.modules.identity.passwords import check_password_rules, hash_password, verify_password
from app.modules.identity.tokens import create_access_token


class EmailAlreadyUsedError(Exception):
    """Raised when a staff member with this email already exists."""


class InvalidRoleError(ValueError):
    """Raised when the role is not one of the allowed job titles."""


def normalise_email(email: str) -> str:
    """Remove stray spaces and capital letters so 'Ada@X.com' equals 'ada@x.com'."""
    return email.strip().lower()


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

def email_is_taken(session: Session, email: str) -> bool:
    """Say whether a staff member already uses this email."""
    clean_email = normalise_email(email)
    return session.exec(select(Staff).where(Staff.email == clean_email)).first() is not None

class InvalidCredentialsError(Exception):
    """Wrong email or password, or the account is switched off."""


# A smoothie of a throwaway password, used to keep timing the same (explained below).
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