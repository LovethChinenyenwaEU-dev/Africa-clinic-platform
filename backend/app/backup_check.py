"""Backups and the restore drill (Week 12). Used by scripts/backup.sh and
scripts/restore_drill.sh; see docs/backup-restore.md.

    python -m app.backup_check heads          # print each clinic's audit-chain head (JSON)
    python -m app.backup_check verify < heads # check a restored database against them

`heads` runs just before a backup. The heads are the anchor for the audit chain (brief
D3): kept beside the backup file, they let a restore prove that the audit log it brings
back is the one that was there, not a rewritten one.

`verify` runs against the restored copy and checks that:
- its migration version is the one this code expects;
- every clinic's audit chain is unbroken, and still has, at each recorded line number,
  the hash written down at backup time (lines added after the heads were read are fine);
- it holds data: the number of rows in the main tables is printed for the drill record.
It prints counts and ids only, never patient data. Exit code 0 means the drill passed.
"""
import json
import sys
import uuid
from dataclasses import dataclass

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine
from app.modules.audit.chain import check_audit_chain

COUNTED_TABLES = (
    "tenant",
    "staff",
    "patient",
    "appointment",
    "encounter",
    "consent",
    "invoice",
    "payment",
    "audit_event",
)


@dataclass(frozen=True)
class Head:
    seq: int
    hash: str


def read_heads(session: Session) -> dict[str, Head]:
    """Each clinic's latest audit line number and hash, as the database keeps them."""
    rows = session.execute(
        text("SELECT tenant_id, last_seq, last_hash FROM audit_chain_head ORDER BY tenant_id")
    ).all()
    return {str(tenant_id): Head(int(seq), str(digest)) for tenant_id, seq, digest in rows}


def expected_revision() -> str:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    return script.get_current_head() or ""


def restored_revision(session: Session) -> str:
    return str(session.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def hash_at(session: Session, tenant_id: str, seq: int) -> str | None:
    return session.execute(
        text("SELECT row_hash FROM audit_event WHERE tenant_id = :t AND chain_seq = :s"),
        {"t": tenant_id, "s": seq},
    ).scalar_one_or_none()


def check_restore(session: Session, heads: dict[str, Head], *, revision: str) -> list[str]:
    """Everything wrong with the restored copy; an empty list means it passed."""
    problems = []
    found = restored_revision(session)
    if found != revision:
        problems.append(f"Migration version is {found}, this code expects {revision}.")
    for tenant_id, head in heads.items():
        chain = check_audit_chain(session, tenant_id=uuid.UUID(tenant_id))
        if not chain.ok:
            problems.append(
                f"Clinic {tenant_id}: audit chain broken at line {chain.broken_at}: "
                f"{chain.problem}"
            )
        elif chain.head_seq < head.seq:
            problems.append(
                f"Clinic {tenant_id}: the restored audit log ends at line {chain.head_seq}, "
                f"but line {head.seq} existed at backup time."
            )
        elif hash_at(session, tenant_id, head.seq) != head.hash:
            problems.append(
                f"Clinic {tenant_id}: line {head.seq} is not the line recorded at backup time."
            )
    return problems


def row_counts(session: Session) -> dict[str, int]:
    return {
        table: int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in COUNTED_TABLES
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else ""
    with Session(engine) as session:
        if command == "heads":
            heads = read_heads(session)
            print(json.dumps({t: {"seq": h.seq, "hash": h.hash} for t, h in heads.items()}))
            return 0
        if command == "verify":
            raw = json.load(sys.stdin)
            heads = {t: Head(int(v["seq"]), str(v["hash"])) for t, v in raw.items()}
            problems = check_restore(session, heads, revision=expected_revision())
            for table, count in row_counts(session).items():
                print(f"  {table:<12} {count} rows")
            print(f"  audit chains checked against {len(heads)} recorded head(s)")
            for problem in problems:
                print(f"PROBLEM: {problem}")
            print("RESTORE DRILL PASSED" if not problems else "RESTORE DRILL FAILED")
            return 0 if not problems else 1
    print("Use: python -m app.backup_check heads | verify < heads.json", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
