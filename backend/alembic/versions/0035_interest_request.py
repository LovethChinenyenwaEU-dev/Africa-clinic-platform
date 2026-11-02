"""interest_request: "Register interest" forms from the public landing page

Not clinic data, so no tenant_id and no tenant_wall policy: nobody in a clinic reads it.
The platform owner reads it with `python -m app.cli list-interest`; rows older than a year
are deleted by the worker.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interest_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("organisation", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interest_request_created_at", "interest_request", ["created_at"])
    op.create_index(
        "ix_interest_request_email_created_at", "interest_request", ["email", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_interest_request_email_created_at", table_name="interest_request")
    op.drop_index("ix_interest_request_created_at", table_name="interest_request")
    op.drop_table("interest_request")
