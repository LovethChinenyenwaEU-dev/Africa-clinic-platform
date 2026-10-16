"""follow_up and referral: what happens after an encounter (FR-C5)

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_keys() -> list[sa.ForeignKeyConstraint]:
    """Fresh constraints for each table: one object cannot belong to two tables."""
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounter.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["staff.id"]),
    ]


def upgrade() -> None:
    text = sqlmodel.sql.sqltypes.AutoString
    moment = sa.DateTime(timezone=True)
    op.create_table(
        "follow_up",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("visit_type", text(), nullable=False),
        sa.Column("instructions", text(), nullable=True),
        sa.Column("status", text(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", moment, nullable=False),
        sa.Column("written_at", moment, nullable=False),
        sa.Column("synced_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_common_keys(),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_up_tenant_id", "follow_up", ["tenant_id"])
    op.create_index("ix_follow_up_encounter_id", "follow_up", ["encounter_id"])
    op.create_index(
        "ix_follow_up_tenant_status_due", "follow_up", ["tenant_id", "status", "due_date"]
    )

    op.create_table(
        "referral",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("to_name", text(), nullable=False),
        sa.Column("specialty", text(), nullable=True),
        sa.Column("urgency", text(), nullable=False),
        sa.Column("reason", text(), nullable=False),
        sa.Column("status", text(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", moment, nullable=False),
        sa.Column("written_at", moment, nullable=False),
        sa.Column("synced_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_common_keys(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_referral_tenant_id", "referral", ["tenant_id"])
    op.create_index(
        "ix_referral_encounter_recorded_at", "referral", ["encounter_id", "recorded_at"]
    )


def downgrade() -> None:
    op.drop_table("referral")
    op.drop_table("follow_up")
