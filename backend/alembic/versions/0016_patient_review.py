"""patient: flag offline registrations that may be duplicates, for a person to review

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-16

Existing patients were all registered online, past the duplicate question, so they
have no review status.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patient", sa.Column("review_status", sa.String(), nullable=True))
    op.add_column("patient", sa.Column("duplicate_of_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_patient_duplicate_of_id_patient", "patient", "patient", ["duplicate_of_id"], ["id"]
    )
    # The review list asks "who in this clinic needs review?".
    op.create_index(
        "ix_patient_tenant_review_status", "patient", ["tenant_id", "review_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_patient_tenant_review_status", table_name="patient")
    op.drop_constraint("fk_patient_duplicate_of_id_patient", "patient", type_="foreignkey")
    op.drop_column("patient", "duplicate_of_id")
    op.drop_column("patient", "review_status")
