"""payment, receipt_counter: cash and transfer payments against issued invoices

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("receipt_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("received_by_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["received_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "receipt_number", name="uq_payment_tenant_receipt"),
        sa.CheckConstraint("amount_kobo > 0", name="ck_payment_amount"),
        sa.CheckConstraint("method IN ('cash', 'transfer')", name="ck_payment_method"),
        sa.CheckConstraint(
            "method <> 'transfer' OR reference IS NOT NULL", name="ck_payment_transfer_reference"
        ),
    )
    op.create_index("ix_payment_tenant_id", "payment", ["tenant_id"])
    op.create_index("ix_payment_invoice_id", "payment", ["invoice_id"])
    # The daily takings (Step 6) ask "what came in today?".
    op.create_index("ix_payment_tenant_received_at", "payment", ["tenant_id", "received_at"])
    # One bank transfer is recorded once, whatever the capitals or spaces typed.
    op.create_index(
        "uq_payment_transfer_reference",
        "payment",
        ["tenant_id", sa.text("lower(reference)")],
        unique=True,
        postgresql_where=sa.text("method = 'transfer'"),
    )

    op.create_table(
        "receipt_counter",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("receipt_counter")
    op.drop_index("uq_payment_transfer_reference", table_name="payment")
    op.drop_index("ix_payment_tenant_received_at", table_name="payment")
    op.drop_index("ix_payment_invoice_id", table_name="payment")
    op.drop_index("ix_payment_tenant_id", table_name="payment")
    op.drop_table("payment")
