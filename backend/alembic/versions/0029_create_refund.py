"""refund, refund_counter: refunds asked by front desk or billing, decided by an admin

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refund",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("refund_number", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payment.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["decided_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "refund_number", name="uq_refund_tenant_number"),
        sa.CheckConstraint("amount_kobo > 0", name="ck_refund_amount"),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'rejected')", name="ck_refund_status"
        ),
        sa.CheckConstraint("method IN ('cash', 'transfer')", name="ck_refund_method"),
        # FR-B3: whoever asked never decides. The database holds the line too.
        sa.CheckConstraint(
            "decided_by_id IS NULL OR decided_by_id <> requested_by_id",
            name="ck_refund_two_people",
        ),
        sa.CheckConstraint(
            "status <> 'approved' OR refund_number IS NOT NULL",
            name="ck_refund_approved_has_number",
        ),
    )
    op.create_index("ix_refund_tenant_id", "refund", ["tenant_id"])
    op.create_index("ix_refund_invoice_id", "refund", ["invoice_id"])
    op.create_index("ix_refund_payment_id", "refund", ["payment_id"])
    # The admin's list of refunds waiting for a decision.
    op.create_index("ix_refund_tenant_status", "refund", ["tenant_id", "status"])

    op.create_table(
        "refund_counter",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("refund_counter")
    op.drop_index("ix_refund_tenant_status", table_name="refund")
    op.drop_index("ix_refund_payment_id", table_name="refund")
    op.drop_index("ix_refund_invoice_id", table_name="refund")
    op.drop_index("ix_refund_tenant_id", table_name="refund")
    op.drop_table("refund")
