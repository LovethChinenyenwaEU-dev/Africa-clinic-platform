import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(SQLModel, table=True):
    """A clinic organisation. Owns branches, staff and patients."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    plan: str = "starter"
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Branch(SQLModel, table=True):
    """One clinic location. Every tenant-owned table carries tenant_id."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    name: str
    city: str = ""
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
