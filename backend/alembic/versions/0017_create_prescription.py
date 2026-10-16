"""prescription: medicines prescribed in an encounter, versioned like the rest of the record

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    text = sqlmodel.sql.sqltypes.AutoString
    op.create_table(
        "prescription",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("version_status", text(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("medicine", text(), nullable=False),
        sa.Column("strength", text(), nullable=True),
        sa.Column("dose", text(), nullable=False),
        sa.Column("route", text(), nullable=False),
        sa.Column("frequency", text(), nullable=False),
        sa.Column("duration", text(), nullable=False),
        sa.Column("instructions", text(), nullable=True),
        sa.Column("clinical_status", text(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["prescription.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prescription_tenant_id", "prescription", ["tenant_id"])
    op.create_index(
        "ix_prescription_encounter_recorded_at", "prescription", ["encounter_id", "recorded_at"]
    )
    op.create_index(
        "ix_prescription_tenant_patient_status",
        "prescription",
        ["tenant_id", "patient_id", "version_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_prescription_tenant_patient_status", table_name="prescription")
    op.drop_index("ix_prescription_encounter_recorded_at", table_name="prescription")
    op.drop_index("ix_prescription_tenant_id", table_name="prescription")
    op.drop_table("prescription")
