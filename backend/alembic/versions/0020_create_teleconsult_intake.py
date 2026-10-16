"""teleconsult_intake: reason and danger-sign screen before a remote visit

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    text = sqlmodel.sql.sqltypes.AutoString
    op.create_table(
        "teleconsult_intake",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("reason", text(), nullable=False),
        sa.Column("red_flags", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("outcome", text(), nullable=False),
        sa.Column("source", text(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teleconsult_intake_tenant_id", "teleconsult_intake", ["tenant_id"])
    op.create_index(
        "ix_teleconsult_intake_appointment_recorded_at",
        "teleconsult_intake",
        ["appointment_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_teleconsult_intake_appointment_recorded_at", table_name="teleconsult_intake")
    op.drop_index("ix_teleconsult_intake_tenant_id", table_name="teleconsult_intake")
    op.drop_table("teleconsult_intake")
