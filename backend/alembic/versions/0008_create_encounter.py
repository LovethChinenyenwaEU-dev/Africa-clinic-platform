"""create encounter table

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "encounter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("clinician_id", sa.Uuid(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["clinician_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["closed_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id", name="uq_encounter_appointment"),
    )
    op.create_index(op.f("ix_encounter_tenant_id"), "encounter", ["tenant_id"], unique=False)
    op.create_index(
        "ix_encounter_tenant_patient_opened_at",
        "encounter",
        ["tenant_id", "patient_id", "opened_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_encounter_tenant_patient_opened_at", table_name="encounter")
    op.drop_index(op.f("ix_encounter_tenant_id"), table_name="encounter")
    op.drop_table("encounter")
