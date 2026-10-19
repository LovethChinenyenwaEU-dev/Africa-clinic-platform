"""patient_summary: plain-language visit summaries, approved by the clinician (FR-R4)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    moment = sa.DateTime(timezone=True)
    op.create_table(
        "patient_summary",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=False),
        sa.Column("drafted_at", moment, nullable=False),
        sa.Column("updated_at", moment, nullable=False),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", moment, nullable=True),
        sa.Column("withdrawn_by_id", sa.Uuid(), nullable=True),
        sa.Column("withdrawn_at", moment, nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["drafted_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["withdrawn_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_summary_tenant_id", "patient_summary", ["tenant_id"])
    op.create_index("ix_patient_summary_encounter_id", "patient_summary", ["encounter_id"])
    op.create_index(
        "ix_patient_summary_patient_status",
        "patient_summary",
        ["tenant_id", "patient_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("patient_summary")
