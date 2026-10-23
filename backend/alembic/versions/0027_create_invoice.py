"""invoice, invoice_line, invoice_counter: one invoice per visit, built from the price list

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("number", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("total_kobo", sa.BigInteger(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_id", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["issued_by_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["voided_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_invoice_tenant_number"),
        sa.CheckConstraint("status IN ('draft', 'issued', 'void')", name="ck_invoice_status"),
        # An issued invoice always has its number and total frozen with it.
        sa.CheckConstraint(
            "status <> 'issued' OR (number IS NOT NULL AND issued_at IS NOT NULL)",
            name="ck_invoice_issued_has_number",
        ),
    )
    op.create_index("ix_invoice_tenant_id", "invoice", ["tenant_id"])
    op.create_index("ix_invoice_patient_id", "invoice", ["patient_id"])
    # One live invoice per visit; a voided draft does not count.
    op.create_index(
        "uq_invoice_live_per_visit",
        "invoice",
        ["appointment_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'void'"),
    )

    op.create_table(
        "invoice_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("price_item_id", sa.Uuid(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("unit_price_kobo", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("added_by_id", sa.Uuid(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"]),
        sa.ForeignKeyConstraint(["price_item_id"], ["price_item.id"]),
        sa.ForeignKeyConstraint(["added_by_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 100", name="ck_invoice_line_quantity"),
        sa.CheckConstraint("unit_price_kobo >= 0", name="ck_invoice_line_price"),
        sa.CheckConstraint(
            "amount_kobo = unit_price_kobo * quantity", name="ck_invoice_line_amount"
        ),
    )
    op.create_index("ix_invoice_line_tenant_id", "invoice_line", ["tenant_id"])
    op.create_index("ix_invoice_line_invoice_id", "invoice_line", ["invoice_id"])

    op.create_table(
        "invoice_counter",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("invoice_counter")
    op.drop_index("ix_invoice_line_invoice_id", table_name="invoice_line")
    op.drop_index("ix_invoice_line_tenant_id", table_name="invoice_line")
    op.drop_table("invoice_line")
    op.drop_index("uq_invoice_live_per_visit", table_name="invoice")
    op.drop_index("ix_invoice_patient_id", table_name="invoice")
    op.drop_index("ix_invoice_tenant_id", table_name="invoice")
    op.drop_table("invoice")
