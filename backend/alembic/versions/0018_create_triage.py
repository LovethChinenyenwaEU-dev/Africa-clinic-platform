"""triage: urgency and danger signs for a waiting patient, newest row counts

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "triage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("level", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("red_flags", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_triage_tenant_id", "triage", ["tenant_id"])
    op.create_index(
        "ix_triage_appointment_recorded_at", "triage", ["appointment_id", "recorded_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_triage_appointment_recorded_at", table_name="triage")
    op.drop_index("ix_triage_tenant_id", table_name="triage")
    op.drop_table("triage")
