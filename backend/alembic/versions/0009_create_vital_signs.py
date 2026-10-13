"""create vital_signs table

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vital_signs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("systolic_mmhg", sa.Integer(), nullable=True),
        sa.Column("diastolic_mmhg", sa.Integer(), nullable=True),
        sa.Column("pulse_bpm", sa.Integer(), nullable=True),
        sa.Column("respiratory_rate", sa.Integer(), nullable=True),
        sa.Column("spo2_pct", sa.Integer(), nullable=True),
        sa.Column("temperature_c", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["vital_signs.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vital_signs_tenant_id"), "vital_signs", ["tenant_id"], unique=False)
    op.create_index(
        "ix_vital_signs_encounter_recorded_at",
        "vital_signs",
        ["encounter_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_vital_signs_tenant_patient_measured_at",
        "vital_signs",
        ["tenant_id", "patient_id", "measured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vital_signs_tenant_patient_measured_at", table_name="vital_signs")
    op.drop_index("ix_vital_signs_encounter_recorded_at", table_name="vital_signs")
    op.drop_index(op.f("ix_vital_signs_tenant_id"), table_name="vital_signs")
    op.drop_table("vital_signs")
