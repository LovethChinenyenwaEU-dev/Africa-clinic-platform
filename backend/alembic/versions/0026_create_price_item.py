"""price_item: the clinic's services and their prices, in kobo

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("price_kobo", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("price_kobo >= 0", name="ck_price_item_price"),
    )
    op.create_index("ix_price_item_tenant_id", "price_item", ["tenant_id"])
    # Two active services of one clinic never share a name, whatever the capitals.
    op.create_index(
        "uq_price_item_active_name",
        "price_item",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_index("uq_price_item_active_name", table_name="price_item")
    op.drop_index("ix_price_item_tenant_id", table_name="price_item")
    op.drop_table("price_item")
