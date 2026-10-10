import uuid

from sqlmodel import Session, SQLModel, col, select


def _require_tenant_column(model: type[SQLModel]) -> None:
    if not hasattr(model, "tenant_id"):
        raise TypeError(f"{model.__name__} has no tenant_id column, so it cannot be tenant-scoped.")


def tenant_select(model: type[SQLModel], tenant_id: uuid.UUID):
    """A SELECT that can only ever see one clinic's rows."""
    _require_tenant_column(model)
    return select(model).where(col(model.tenant_id) == tenant_id)


def get_in_tenant(
    session: Session,
    model: type[SQLModel],
    *,
    tenant_id: uuid.UUID,
    row_id: uuid.UUID,
) -> SQLModel | None:
    """Find one row by ID, but only if it belongs to this clinic. Otherwise None."""
    _require_tenant_column(model)
    statement = tenant_select(model, tenant_id).where(col(model.id) == row_id)
    return session.exec(statement).first()