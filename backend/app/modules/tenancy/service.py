import uuid

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.tenancy.models import Branch, Tenant


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


def create_branch(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    name: str,
    city: str = "",
) -> Branch:
    """Create a branch inside one clinic."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Branch name cannot be empty.")

    branch = Branch(tenant_id=tenant_id, name=clean_name, city=city.strip())
    session.add(branch)
    session.commit()
    session.refresh(branch)
    return branch


def list_branches(session: Session, *, tenant_id: uuid.UUID) -> list[Branch]:
    """Every branch of this clinic, and no other clinic's."""
    statement = tenant_select(Branch, tenant_id).order_by(col(Branch.name))
    return list(session.exec(statement).all())


def get_branch(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> Branch | None:
    """One branch, but only if it belongs to this clinic."""
    branch = get_in_tenant(session, Branch, tenant_id=tenant_id, row_id=branch_id)
    return branch if isinstance(branch, Branch) else None