"""consent and appointment: allow the patient to agree and book on their own page

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-21

recorded_by_id / created_by_id point at a staff member, so they may now be empty when
the patient did it themselves; the new *_via column says which. Existing rows were all
done by staff.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("consent", "recorded_by_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column(
        "consent",
        sa.Column("recorded_via", sa.String(), nullable=False, server_default="staff"),
    )
    op.alter_column("appointment", "created_by_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column(
        "appointment",
        sa.Column("booked_via", sa.String(), nullable=False, server_default="staff"),
    )


def downgrade() -> None:
    # Only safe while no patient has agreed or booked on their own page.
    op.drop_column("appointment", "booked_via")
    op.alter_column("appointment", "created_by_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("consent", "recorded_via")
    op.alter_column("consent", "recorded_by_id", existing_type=sa.Uuid(), nullable=False)
