"""online_payment: Paystack payment links; payments may now be made online

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_payment_method", "payment", type_="check")
    op.create_check_constraint(
        "ck_payment_method", "payment", "method IN ('cash', 'transfer', 'paystack')"
    )
    # A gateway reference, like a bank transfer reference, is recorded once per clinic:
    # FR-B4, a repeated webhook can never credit an invoice twice.
    op.drop_index("uq_payment_transfer_reference", table_name="payment")
    op.create_index(
        "uq_payment_transfer_reference",
        "payment",
        ["tenant_id", sa.text("lower(reference)")],
        unique=True,
        postgresql_where=sa.text("method IN ('transfer', 'paystack')"),
    )

    op.create_table(
        "online_payment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("gateway", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("link", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("failure_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "gateway_transaction_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payment.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
        sa.UniqueConstraint("payment_id"),
        sa.CheckConstraint("amount_kobo > 0", name="ck_online_payment_amount"),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name="ck_online_payment_status"
        ),
        # Succeeded always means one real payment row behind it.
        sa.CheckConstraint(
            "status <> 'succeeded' OR payment_id IS NOT NULL",
            name="ck_online_payment_succeeded_has_payment",
        ),
    )
    op.create_index("ix_online_payment_tenant_id", "online_payment", ["tenant_id"])
    op.create_index("ix_online_payment_invoice_id", "online_payment", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_online_payment_invoice_id", table_name="online_payment")
    op.drop_index("ix_online_payment_tenant_id", table_name="online_payment")
    op.drop_table("online_payment")
    op.drop_index("uq_payment_transfer_reference", table_name="payment")
    op.create_index(
        "uq_payment_transfer_reference",
        "payment",
        ["tenant_id", sa.text("lower(reference)")],
        unique=True,
        postgresql_where=sa.text("method = 'transfer'"),
    )
    op.drop_constraint("ck_payment_method", "payment", type_="check")
    op.create_check_constraint(
        "ck_payment_method", "payment", "method IN ('cash', 'transfer')"
    )
