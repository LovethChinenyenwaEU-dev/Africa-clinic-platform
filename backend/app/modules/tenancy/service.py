from sqlmodel import Session

from app.modules.tenancy.models import Tenant


def create_tenant(session: Session, *, name: str) -> Tenant:
    """Create a clinic (tenant)."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Clinic name cannot be empty.")

    tenant = Tenant(name=clean_name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant