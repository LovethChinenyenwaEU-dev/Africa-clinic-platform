"""create clinical_note table

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinical_note",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("version_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["clinical_note.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clinical_note_tenant_id"), "clinical_note", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_clinical_note_encounter_recorded_at",
        "clinical_note",
        ["encounter_id", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_clinical_note_encounter_recorded_at", table_name="clinical_note")
    op.drop_index(op.f("ix_clinical_note_tenant_id"), table_name="clinical_note")
    op.drop_table("clinical_note")
