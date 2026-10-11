"""create audit_event table, append-only

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_event_tenant_id"), "audit_event", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_audit_event_patient_id"), "audit_event", ["patient_id"], unique=False)

    # The lock inside the database: rows can be added, never changed or removed.
    op.execute(
        """
        CREATE FUNCTION audit_event_block_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event rows cannot be changed or deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_block_changes();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_event_no_update_delete ON audit_event")
    op.execute("DROP FUNCTION audit_event_block_changes()")
    op.drop_index(op.f("ix_audit_event_patient_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_tenant_id"), table_name="audit_event")
    op.drop_table("audit_event")