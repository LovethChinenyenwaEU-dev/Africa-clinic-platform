"""row-level security: the database keeps clinics apart too (brief D2)

A role, clinic_app, that may read and write the tables but owns none of them, so
PostgreSQL applies row-level security to it. Each table with a tenant_id gets a policy:
clinic_app sees, adds and changes only rows whose tenant_id is the current
app.tenant_id. Once a request knows who is signed in, the app runs each transaction as
clinic_app with that clinic (app/core/tenant_wall.py).

Left outside the wall on purpose:
- staff: an email address must be unique across every clinic, so that check must see
  them all; the table holds no patient data;
- audit_chain_head: the audit chain's counter, written by the audit trigger.

A new table with a tenant_id must get the same policy; a test fails until it does.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-30
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "clinic_app"
OUTSIDE_THE_WALL = ("staff", "audit_chain_head")
# The rule itself, as it goes inside format(...): quotes doubled.
THIS_CLINIC = "tenant_id = nullif(current_setting(''app.tenant_id'', true), '''')::uuid"

# Every table in the schema with a tenant_id column, except those left outside.
_TENANT_TABLES = f"""
    SELECT c.table_name FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'
      AND t.table_type = 'BASE TABLE'
      AND c.table_name NOT IN ({", ".join(f"'{name}'" for name in OUTSIDE_THE_WALL)})
"""


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END $$;
        """
    )
    # The app's own login may switch to this role (SET ROLE) for walled work.
    op.execute(f"GRANT {APP_ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    # Tables that later migrations create get the same rights.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
    )
    op.execute(
        f"""
        DO $$
        DECLARE
            tbl text;
        BEGIN
            FOR tbl IN {_TENANT_TABLES}
            LOOP
                EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
                EXECUTE format(
                    'CREATE POLICY tenant_wall ON %I TO {APP_ROLE} '
                    'USING ({THIS_CLINIC}) WITH CHECK ({THIS_CLINIC})',
                    tbl
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            tbl text;
        BEGIN
            FOR tbl IN
                SELECT tablename FROM pg_policies
                WHERE schemaname = 'public' AND policyname = 'tenant_wall'
            LOOP
                EXECUTE format('DROP POLICY tenant_wall ON %I', tbl);
                EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', tbl);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE}"
    )
    op.execute(f"DROP OWNED BY {APP_ROLE}")
    op.execute(f"DROP ROLE {APP_ROLE}")
