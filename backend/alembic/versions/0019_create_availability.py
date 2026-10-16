"""availability: clinicians' weekly hours, in person or remote, cut into slots

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "availability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("clinician_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("starts", sa.Time(), nullable=False),
        sa.Column("ends", sa.Time(), nullable=False),
        sa.Column("visit_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["clinician_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        sa.CheckConstraint("starts < ends", name="ck_availability_order"),
    )
    op.create_index("ix_availability_tenant_id", "availability", ["tenant_id"])
    op.create_index(
        "ix_availability_clinician_weekday", "availability", ["clinician_id", "weekday"]
    )


def downgrade() -> None:
    op.drop_index("ix_availability_clinician_weekday", table_name="availability")
    op.drop_index("ix_availability_tenant_id", table_name="availability")
    op.drop_table("availability")
