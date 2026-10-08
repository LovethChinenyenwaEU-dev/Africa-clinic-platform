import uuid

from sqlmodel import Session, select

from app.modules.identity.models import Role, Staff
from app.modules.identity.passwords import check_password_rules, hash_password


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

    clean_email = normalise_email(email)
    existing = session.exec(select(Staff).where(Staff.email == clean_email)).first()
    if existing is not None:
        raise EmailAlreadyUsedError("A staff member with this email already exists.")

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