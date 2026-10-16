"""consult_room, consult_mode_change, consult_message: the remote visit's room and chat

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    text = sqlmodel.sql.sqltypes.AutoString
    moment = sa.DateTime(timezone=True)
    op.create_table(
        "consult_room",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("provider", text(), nullable=False),
        sa.Column("room_name", text(), nullable=False),
        sa.Column("mode", text(), nullable=False),
        sa.Column("opened_by_id", sa.Uuid(), nullable=False),
        sa.Column("opened_at", moment, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["opened_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("ix_consult_room_tenant_id", "consult_room", ["tenant_id"])

    op.create_table(
        "consult_mode_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("from_mode", text(), nullable=False),
        sa.Column("to_mode", text(), nullable=False),
        sa.Column("reason", text(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("changed_at", moment, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["changed_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consult_mode_change_tenant_id", "consult_mode_change", ["tenant_id"])
    op.create_index(
        "ix_consult_mode_change_appointment_id", "consult_mode_change", ["appointment_id"]
    )

    op.create_table(
        "consult_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("sender", text(), nullable=False),
        sa.Column("sender_staff_id", sa.Uuid(), nullable=True),
        sa.Column("body", text(), nullable=False),
        sa.Column("sent_at", moment, nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["sender_staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consult_message_tenant_id", "consult_message", ["tenant_id"])
    op.create_index(
        "ix_consult_message_appointment_sent_at", "consult_message", ["appointment_id", "sent_at"]
    )


def downgrade() -> None:
    op.drop_table("consult_message")
    op.drop_table("consult_mode_change")
    op.drop_table("consult_room")
