"""The clinic's price list: services and what they cost (Week 10 Step 1).

Only an admin adds or changes a price; everyone who books or bills reads the list.
Amounts are whole kobo (100 kobo = 1 naira), so there is never a rounding error.
A price list holds no patient data, so reading it writes no diary line; every
addition and change does, so an odd price change can be traced to a person.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.billing.models import PriceItem

MAX_NAME_LENGTH = 120
MAX_CODE_LENGTH = 20
MAX_PRICE_KOBO = 1_000_000_000  # 10 million naira for one service: anything above is a typo


class InvalidPriceError(ValueError):
    """The name, code or amount is not acceptable."""


class PriceNameTakenError(Exception):
    """Another active service of this clinic already has this name."""


class PriceNotFoundError(Exception):
    """No such service in this clinic."""


def _clean(name: str, code: str | None, price_kobo: int) -> tuple[str, str | None, int]:
    clean_name = " ".join(name.split())
    if not clean_name:
        raise InvalidPriceError("Give the service a name.")
    if len(clean_name) > MAX_NAME_LENGTH:
        raise InvalidPriceError(f"The name must be at most {MAX_NAME_LENGTH} characters.")
    clean_code = code.strip().upper() if code and code.strip() else None
    if clean_code is not None and len(clean_code) > MAX_CODE_LENGTH:
        raise InvalidPriceError(f"The code must be at most {MAX_CODE_LENGTH} characters.")
    # bool is an int in Python; True must not become 1 kobo.
    if isinstance(price_kobo, bool) or not isinstance(price_kobo, int):
        raise InvalidPriceError("The price must be a whole number of kobo.")
    if not 0 <= price_kobo <= MAX_PRICE_KOBO:
        raise InvalidPriceError("The price must be between 0 and 10,000,000 naira.")
    return clean_name, clean_code, price_kobo


def _name_taken(
    session: Session, *, tenant_id: uuid.UUID, name: str, except_id: uuid.UUID | None = None
) -> bool:
    statement = (
        tenant_select(PriceItem, tenant_id)
        .where(col(PriceItem.active))
        .where(func.lower(col(PriceItem.name)) == name.lower())
    )
    if except_id is not None:
        statement = statement.where(col(PriceItem.id) != except_id)
    return session.exec(statement).first() is not None


def _save(session: Session, row: PriceItem) -> PriceItem:
    try:
        session.commit()
    except IntegrityError:
        # Two people saved the same name at the same moment: the index caught it.
        session.rollback()
        raise PriceNameTakenError("Another service already has this name.") from None
    session.refresh(row)
    return row


def add_price(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    price_kobo: int,
    code: str | None = None,
    price_id: uuid.UUID | None = None,
) -> PriceItem:
    """Add a service to the price list. Sending the same ID twice adds it once."""
    if price_id is not None:
        existing = get_in_tenant(session, PriceItem, tenant_id=tenant_id, row_id=price_id)
        if isinstance(existing, PriceItem):
            return existing
    clean_name, clean_code, amount = _clean(name, code, price_kobo)
    if _name_taken(session, tenant_id=tenant_id, name=clean_name):
        raise PriceNameTakenError("Another service already has this name.")

    row = PriceItem(
        id=price_id or uuid.uuid4(),
        tenant_id=tenant_id,
        name=clean_name,
        code=clean_code,
        price_kobo=amount,
        created_by_id=actor_id,
    )
    session.add(row)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRICE_ADD,
        entity_id=row.id,
    )
    return _save(session, row)


def change_price(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    price_id: uuid.UUID,
    name: str,
    code: str | None,
    price_kobo: int,
    active: bool,
) -> PriceItem:
    """Change a service: its name, code, price, or retire it (active False) or bring it back.

    Invoices already written keep the name and price they copied.
    Sending exactly what is already there changes nothing and writes no diary line.
    """
    row = get_in_tenant(session, PriceItem, tenant_id=tenant_id, row_id=price_id)
    if not isinstance(row, PriceItem):
        raise PriceNotFoundError("Service not found.")
    clean_name, clean_code, amount = _clean(name, code, price_kobo)
    if (row.name, row.code, row.price_kobo, row.active) == (clean_name, clean_code, amount, active):
        return row
    if active and _name_taken(session, tenant_id=tenant_id, name=clean_name, except_id=row.id):
        raise PriceNameTakenError("Another service already has this name.")

    row.name = clean_name
    row.code = clean_code
    row.price_kobo = amount
    row.active = active
    row.updated_by_id = actor_id
    row.updated_at = datetime.now(UTC)
    session.add(row)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.PRICE_CHANGE,
        entity_id=row.id,
    )
    return _save(session, row)


def list_prices(
    session: Session, *, tenant_id: uuid.UUID, include_retired: bool = False
) -> list[PriceItem]:
    """The clinic's services, A to Z. Retired ones only when asked for."""
    statement = tenant_select(PriceItem, tenant_id).order_by(func.lower(col(PriceItem.name)))
    if not include_retired:
        statement = statement.where(col(PriceItem.active))
    return list(session.exec(statement).all())


def get_price(session: Session, *, tenant_id: uuid.UUID, price_id: uuid.UUID) -> PriceItem:
    """One service of this clinic, active or retired."""
    row = get_in_tenant(session, PriceItem, tenant_id=tenant_id, row_id=price_id)
    if not isinstance(row, PriceItem):
        raise PriceNotFoundError("Service not found.")
    return row
