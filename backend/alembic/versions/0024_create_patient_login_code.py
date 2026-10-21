"""patient_login_code: one-time SMS sign-in codes for the patient web pages

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    moment = sa.DateTime(timezone=True)
    op.create_table(
        "patient_login_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", moment, nullable=False),
        sa.Column("expires_at", moment, nullable=False),
        sa.Column("used_at", moment, nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_login_code_tenant_id", "patient_login_code", ["tenant_id"])
    op.create_index(
        "ix_patient_login_code_phone_created",
        "patient_login_code",
        ["tenant_id", "phone", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("patient_login_code")
