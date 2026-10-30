"""staff_session: one row per signed-in device, so one device can be signed out alone

The access token carries the row's id ("sid"); every request checks the row is still
open. It carries a tenant_id, so it gets the tenant_wall policy (migration 0032).

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THIS_CLINIC = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "staff_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["ended_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_session_tenant_id", "staff_session", ["tenant_id"])
    op.create_index("ix_staff_session_staff_id", "staff_session", ["staff_id"])

    op.execute("ALTER TABLE staff_session ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_wall ON staff_session TO clinic_app "
        f"USING ({THIS_CLINIC}) WITH CHECK ({THIS_CLINIC})"
    )


def downgrade() -> None:
    op.drop_index("ix_staff_session_staff_id", table_name="staff_session")
    op.drop_index("ix_staff_session_tenant_id", table_name="staff_session")
    op.drop_table("staff_session")
