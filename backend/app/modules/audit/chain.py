"""Checking the tamper-evident audit chain (Week 11, brief D3).

The database numbers and hashes every audit line as it is added (migration 0031).
This check asks the database to recompute each line's hash with the same function and
to compare each line's "previous hash" with the line before it. Any line changed,
removed or slipped in afterwards shows up as the first place the chain breaks.

What it cannot see on its own: someone who rewrites the WHOLE chain from a point
onwards. That is why the check answers with the latest number and hash (the "head"):
an admin who writes them down, or keeps the daily export, can later prove the chain
still runs through the same head.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session

from app.modules.audit.service import AuditAction, add_audit_event

GENESIS = "0" * 64  # the "previous hash" of each clinic's first line

_CHECK = text(
    """
    SELECT chain_seq,
           row_hash = audit_event_digest(e) AS hash_ok,
           prev_hash = coalesce(lag(row_hash) OVER w, :genesis) AS link_ok,
           chain_seq = row_number() OVER w AS number_ok,
           row_hash
    FROM audit_event e
    WHERE tenant_id = :tenant_id
    WINDOW w AS (ORDER BY chain_seq)
    ORDER BY chain_seq
    """
)


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    lines_checked: int
    broken_at: int | None  # the first line number where the chain breaks
    problem: str | None
    head_seq: int  # the latest line number
    head_hash: str  # and its hash: write these down to anchor the chain


def check_audit_chain(session: Session, *, tenant_id: uuid.UUID) -> ChainCheck:
    """Recompute this clinic's whole chain. No diary line: see view_audit_chain."""
    rows = session.execute(_CHECK, {"tenant_id": tenant_id, "genesis": GENESIS}).all()
    head_seq, head_hash = 0, GENESIS
    for seq, hash_ok, link_ok, number_ok, row_hash in rows:
        problem = None
        if not number_ok:
            problem = "A line is missing before this one (the numbers jump)."
        elif not link_ok:
            problem = "This line does not follow the one before it (a line was removed or added)."
        elif not hash_ok:
            problem = "This line was changed after it was written."
        if problem:
            return ChainCheck(False, len(rows), int(seq), problem, int(seq), row_hash)
        head_seq, head_hash = int(seq), row_hash
    return ChainCheck(True, len(rows), None, None, head_seq, head_hash)


def view_audit_chain(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID
) -> ChainCheck:
    """The admin's check. Checked first, then the check itself goes in the diary."""
    result = check_audit_chain(session, tenant_id=tenant_id)
    add_audit_event(
        session, tenant_id=tenant_id, actor_id=actor_id, action=AuditAction.AUDIT_VERIFY
    )
    session.commit()
    return result
