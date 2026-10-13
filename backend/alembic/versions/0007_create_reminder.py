"""create reminder table

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminder",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("provider_message_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id", "channel", name="uq_reminder_appointment_channel"),
    )
    op.create_index(op.f("ix_reminder_tenant_id"), "reminder", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_reminder_appointment_id"), "reminder", ["appointment_id"], unique=False
    )
    op.create_index("ix_reminder_status_due_at", "reminder", ["status", "due_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reminder_status_due_at", table_name="reminder")
    op.drop_index(op.f("ix_reminder_appointment_id"), table_name="reminder")
    op.drop_index(op.f("ix_reminder_tenant_id"), table_name="reminder")
    op.drop_table("reminder")
