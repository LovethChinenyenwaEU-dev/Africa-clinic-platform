"""staff_mfa, staff_backup_code: authenticator-app sign-in for admins and billing

Both tables carry a tenant_id, so they get the tenant_wall policy like every other
clinic table (migration 0032).

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THIS_CLINIC = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"


def _wall(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_wall ON {table} TO clinic_app "
        f"USING ({THIS_CLINIC}) WITH CHECK ({THIS_CLINIC})"
    )


def upgrade() -> None:
    op.create_table(
        "staff_mfa",
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("secret", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step", sa.BigInteger(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("staff_id"),
    )
    op.create_index("ix_staff_mfa_tenant_id", "staff_mfa", ["tenant_id"])

    op.create_table(
        "staff_backup_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_backup_code_tenant_id", "staff_backup_code", ["tenant_id"])
    op.create_index("ix_staff_backup_code_staff_id", "staff_backup_code", ["staff_id"])

    _wall("staff_mfa")
    _wall("staff_backup_code")


def downgrade() -> None:
    op.drop_index("ix_staff_backup_code_staff_id", table_name="staff_backup_code")
    op.drop_index("ix_staff_backup_code_tenant_id", table_name="staff_backup_code")
    op.drop_table("staff_backup_code")
    op.drop_index("ix_staff_mfa_tenant_id", table_name="staff_mfa")
    op.drop_table("staff_mfa")
