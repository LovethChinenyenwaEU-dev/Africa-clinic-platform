"""audit_event: record which entity was touched, and index the admin filters

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-14

Adding a column does not fire the append-only trigger: no existing diary line is
changed. Old lines simply have no entity_id.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_event", sa.Column("entity_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_audit_event_tenant_occurred_at",
        "audit_event",
        ["tenant_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_event_tenant_actor_occurred_at",
        "audit_event",
        ["tenant_id", "actor_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_event_tenant_actor_occurred_at", table_name="audit_event")
    op.drop_index("ix_audit_event_tenant_occurred_at", table_name="audit_event")
    op.drop_column("audit_event", "entity_id")
