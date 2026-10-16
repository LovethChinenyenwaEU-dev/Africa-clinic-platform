"""vital_signs and clinical_note: mark entries synced after sign-off; notes keep a device time

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-16

Existing rows were all saved while their encounter was open, so they are not late,
and a note's device time is the time it reached the server.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("vital_signs", "clinical_note"):
        op.add_column(
            table,
            sa.Column("synced_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.add_column(
        "clinical_note", sa.Column("written_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE clinical_note SET written_at = recorded_at")
    op.alter_column("clinical_note", "written_at", nullable=False)


def downgrade() -> None:
    op.drop_column("clinical_note", "written_at")
    for table in ("vital_signs", "clinical_note"):
        op.drop_column(table, "synced_late")
