import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class PriceItem(SQLModel, table=True):
    """One service the clinic charges for, with its price in kobo (100 kobo = 1 naira).

    Never deleted: a service no longer offered is retired (active = False), so old
    invoices can still say what was charged. Invoices copy the name and price when
    they are written, so changing a price never changes an invoice already issued.
    No two active services of one clinic share a name (a unique index in the migration).
    """

    __tablename__ = "price_item"
    __table_args__ = (CheckConstraint("price_kobo >= 0", name="ck_price_item_price"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    name: str
    code: str | None = None  # the clinic's own short code, e.g. "CONS-GP"
    price_kobo: int = Field(sa_column=Column(BigInteger, nullable=False))
    active: bool = True
    created_by_id: uuid.UUID = Field(foreign_key="staff.id")
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_by_id: uuid.UUID | None = Field(default=None, foreign_key="staff.id")
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
