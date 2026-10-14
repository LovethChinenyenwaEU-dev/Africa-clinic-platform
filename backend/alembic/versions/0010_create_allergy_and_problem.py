"""create allergy and problem tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "allergy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("version_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("substance", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("reaction", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("severity", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("clinical_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["allergy.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_allergy_tenant_id"), "allergy", ["tenant_id"], unique=False)
    op.create_index(
        "ix_allergy_tenant_patient_status",
        "allergy",
        ["tenant_id", "patient_id", "version_status"],
        unique=False,
    )

    op.create_table(
        "problem",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("version_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("clinical_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("onset_date", sa.Date(), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["problem.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_problem_tenant_id"), "problem", ["tenant_id"], unique=False)
    op.create_index(
        "ix_problem_tenant_patient_status",
        "problem",
        ["tenant_id", "patient_id", "version_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_problem_tenant_patient_status", table_name="problem")
    op.drop_index(op.f("ix_problem_tenant_id"), table_name="problem")
    op.drop_table("problem")
    op.drop_index("ix_allergy_tenant_patient_status", table_name="allergy")
    op.drop_index(op.f("ix_allergy_tenant_id"), table_name="allergy")
    op.drop_table("allergy")
