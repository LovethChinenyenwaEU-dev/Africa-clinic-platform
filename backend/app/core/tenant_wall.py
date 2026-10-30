"""The database's own wall between clinics (Week 11, brief D2: row-level security).

Every query already filters by clinic in the code (tenant_select). This is the second
wall, inside PostgreSQL: once a request knows who is signed in, each of its transactions
runs as the role `clinic_app` with `app.tenant_id` set to that person's clinic, and the
row-level security policies (migration 0032) let that role see and write only rows of
that clinic. A query that forgets its clinic filter then finds nothing, instead of
another clinic's patients.

Work with nobody signed in (signing in, the patient SMS sign-in, the Paystack webhook,
the reminder worker, migrations) keeps the owner role: it filters by clinic itself.

Both settings are SET LOCAL: they end with the transaction, so a pooled connection never
carries one clinic's wall into the next request.
"""
import uuid

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlmodel import Session

APP_ROLE = "clinic_app"
_INFO_KEY = "tenant_wall"


def _apply(connection: Connection, tenant_id: str) -> None:
    connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
    )


@event.listens_for(Session, "after_begin")
def _on_begin(session: Session, transaction, connection: Connection) -> None:
    """Each new transaction of a walled session starts behind the wall again."""
    tenant_id = session.info.get(_INFO_KEY)
    if tenant_id:
        _apply(connection, tenant_id)


def raise_tenant_wall(session: Session, tenant_id: uuid.UUID) -> None:
    """From now on this session sees and writes only this clinic's rows."""
    already_open = session.in_transaction()
    session.info[_INFO_KEY] = str(tenant_id)
    if already_open:
        # The transaction that loaded the signed-in person is still open: wall it now.
        _apply(session.connection(), str(tenant_id))


def behind_wall(session: Session) -> uuid.UUID | None:
    """The clinic this session is walled to, if any."""
    value = session.info.get(_INFO_KEY)
    return uuid.UUID(value) if value else None
