"""audit_event hash chain: the audit log becomes tamper-evident (brief D3)

Each clinic's audit lines form a chain: every line stores its number in the chain,
the previous line's hash, and its own SHA-256 hash over all its fields and that
previous hash. The database computes them in a trigger when a line is added, so no
code path can skip it. A per-clinic chain head is locked while a line is numbered,
so two lines added at the same moment never share a number.

The append-only trigger (0004) already refuses changes and deletes. This catches what
it cannot: someone with database-owner rights who switches that trigger off, edits or
deletes a line, and switches it back on. The chain breaks at that line, and the check
(GET /api/v1/audit/chain) says where.

Existing lines are chained here, oldest first, so the check covers them too.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENESIS = "0" * 64  # the "previous hash" of each clinic's first line


def upgrade() -> None:
    op.add_column("audit_event", sa.Column("chain_seq", sa.BigInteger(), nullable=True))
    op.add_column("audit_event", sa.Column("prev_hash", sa.String(), nullable=True))
    op.add_column("audit_event", sa.Column("row_hash", sa.String(), nullable=True))

    # The one place the hash is defined. The trigger and the check both use it, so they
    # can never disagree about how a line is written down.
    op.execute(
        """
        CREATE FUNCTION audit_event_digest(e audit_event) RETURNS text
        LANGUAGE sql STABLE AS $$
            SELECT encode(sha256(convert_to(concat_ws('|',
                e.chain_seq::text,
                e.prev_hash,
                e.id::text,
                e.tenant_id::text,
                e.actor_id::text,
                coalesce(e.patient_id::text, '-'),
                coalesce(e.entity_id::text, '-'),
                coalesce(e.device_id::text, '-'),
                e.action,
                coalesce(e.purpose, '-'),
                to_char(e.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
            ), 'UTF8')), 'hex')
        $$;
        """
    )
    op.create_table(
        "audit_chain_head",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        sa.Column("last_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
    )

    # Chain the lines already written, oldest first, clinic by clinic. Filling the new
    # columns is an update, which the append-only trigger refuses: it is switched off for
    # this one statement block only, inside this migration's transaction.
    op.execute("ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update_delete")
    op.execute(
        f"""
        DO $$
        DECLARE
            r record;
            seq bigint := 0;
            prev text := '{GENESIS}';
            clinic uuid := NULL;
        BEGIN
            FOR r IN SELECT id, tenant_id FROM audit_event ORDER BY tenant_id, occurred_at, id
            LOOP
                IF clinic IS DISTINCT FROM r.tenant_id THEN
                    clinic := r.tenant_id;
                    seq := 0;
                    prev := '{GENESIS}';
                END IF;
                seq := seq + 1;
                UPDATE audit_event SET chain_seq = seq, prev_hash = prev WHERE id = r.id;
                UPDATE audit_event e SET row_hash = audit_event_digest(e)
                WHERE e.id = r.id RETURNING row_hash INTO prev;
            END LOOP;
        END $$;
        """
    )
    op.execute("ALTER TABLE audit_event ENABLE TRIGGER audit_event_no_update_delete")
    op.execute(
        """
        INSERT INTO audit_chain_head (tenant_id, last_seq, last_hash)
        SELECT DISTINCT ON (tenant_id) tenant_id, chain_seq, row_hash
        FROM audit_event
        ORDER BY tenant_id, chain_seq DESC
        """
    )
    op.alter_column("audit_event", "chain_seq", nullable=False)
    op.alter_column("audit_event", "prev_hash", nullable=False)
    op.alter_column("audit_event", "row_hash", nullable=False)
    op.create_index(
        "uq_audit_event_tenant_chain_seq", "audit_event", ["tenant_id", "chain_seq"], unique=True
    )

    # Every new line is numbered and hashed by the database itself.
    op.execute(
        f"""
        CREATE FUNCTION audit_event_chain() RETURNS trigger AS $$
        DECLARE
            head record;
        BEGIN
            INSERT INTO audit_chain_head (tenant_id, last_seq, last_hash)
            VALUES (NEW.tenant_id, 0, '{GENESIS}')
            ON CONFLICT (tenant_id) DO NOTHING;
            SELECT last_seq, last_hash INTO head
            FROM audit_chain_head WHERE tenant_id = NEW.tenant_id FOR UPDATE;
            NEW.chain_seq := head.last_seq + 1;
            NEW.prev_hash := head.last_hash;
            NEW.row_hash := audit_event_digest(NEW);
            UPDATE audit_chain_head
            SET last_seq = NEW.chain_seq, last_hash = NEW.row_hash
            WHERE tenant_id = NEW.tenant_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_chain_insert
        BEFORE INSERT ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_chain();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_event_chain_insert ON audit_event")
    op.execute("DROP FUNCTION audit_event_chain()")
    op.drop_index("uq_audit_event_tenant_chain_seq", table_name="audit_event")
    op.drop_table("audit_chain_head")
    op.execute("DROP FUNCTION audit_event_digest(audit_event)")
    op.drop_column("audit_event", "row_hash")
    op.drop_column("audit_event", "prev_hash")
    op.drop_column("audit_event", "chain_seq")
