"""audit_event: record which device a diary line came from (FR-A2)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-16

Adding a column does not fire the append-only trigger: no existing diary line is
changed. Older lines simply have no device.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_event", sa.Column("device_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_event", "device_id")
