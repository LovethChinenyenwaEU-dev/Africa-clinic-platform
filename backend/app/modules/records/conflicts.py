"""Conflicting versions: keep both, let a clinician choose (FR-O4).

Two devices can correct the same version while one of them is offline. The second
correction to arrive starts from a version that is no longer current. It is not
refused (that would lose a clinical write) and it does not overwrite anything:
it is saved with status `conflict`, beside the current version, until a clinician
chooses which one to keep. The one not chosen is kept as superseded. Nothing is
ever deleted.

Vitals keep their version in `status`; allergies, problems and notes in
`version_status`. These helpers hide that difference.
"""
import uuid
from collections.abc import Callable

from sqlmodel import Session, SQLModel, col

from app.core.tenant_scope import tenant_select
from app.modules.records.models import VitalSigns
from app.modules.records.service import NotCurrentVersionError
from app.modules.records.statuses import VersionStatus

CURRENT = VersionStatus.CURRENT.value
SUPERSEDED = VersionStatus.SUPERSEDED.value
CONFLICT = VersionStatus.CONFLICT.value

# What normal lists show: the version in use, and any conflict waiting for a choice.
SHOWN = (CURRENT, CONFLICT)


class NotAConflictError(Exception):
    """Only a version in conflict can be resolved."""


def _field(model: type[SQLModel]) -> str:
    return "status" if model is VitalSigns else "version_status"


def status_of(row: SQLModel) -> str:
    return getattr(row, _field(type(row)))


def set_status(row: SQLModel, value: str) -> None:
    setattr(row, _field(type(row)), value)


def status_column(model: type[SQLModel]):
    return col(getattr(model, _field(model)))


def new_version_status(base: SQLModel) -> str:
    """The status a new version gets when it is made from `base`.

    From the current version: it becomes current. From a version that was already
    replaced elsewhere: it becomes a conflict. From a conflict: refused, so conflicts
    never pile on conflicts; resolve it first.
    """
    status = status_of(base)
    if status == CURRENT:
        return CURRENT
    if status == SUPERSEDED:
        return CONFLICT
    raise NotCurrentVersionError("This version is in conflict. Resolve the conflict first.")


def current_successor(
    session: Session, model: type[SQLModel], *, tenant_id: uuid.UUID, base_id: uuid.UUID
):
    """The version now in use that grew out of `base_id`, or None.

    Follows replaces_id links forward, skipping conflicts, until it finds the
    current version. There is only ever one current version per chain.
    """
    frontier = [base_id]
    seen: set[uuid.UUID] = set()
    while frontier:
        statement = tenant_select(model, tenant_id).where(col(model.replaces_id).in_(frontier))
        children = [row for row in session.exec(statement).all() if row.id not in seen]
        for child in children:
            if status_of(child) == CURRENT:
                return child
        seen.update(child.id for child in children)
        frontier = [child.id for child in children if status_of(child) != CONFLICT]
    return None


def _locked(session: Session, model: type[SQLModel], *, tenant_id: uuid.UUID, row_id):
    statement = tenant_select(model, tenant_id).where(col(model.id) == row_id).with_for_update()
    return session.exec(statement).first()


def resolve_conflict(
    session: Session,
    model: type[SQLModel],
    *,
    tenant_id: uuid.UUID,
    conflict_id: uuid.UUID,
    keep_conflict: bool,
    not_found: type[Exception],
    check_allowed: Callable[[SQLModel, SQLModel | None], None],
):
    """Choose between a conflict and the current version. Returns the version now in use.

    `check_allowed(conflict, current)` raises if this person may not choose.
    Does not commit: the caller adds its diary line and commits once.
    """
    conflict = _locked(session, model, tenant_id=tenant_id, row_id=conflict_id)
    if conflict is None:
        raise not_found("Not found.")
    if status_of(conflict) != CONFLICT:
        raise NotAConflictError("This version is not in conflict.")
    current = current_successor(session, model, tenant_id=tenant_id, base_id=conflict.replaces_id)
    if current is not None:
        current = _locked(session, model, tenant_id=tenant_id, row_id=current.id)
    check_allowed(conflict, current)

    if keep_conflict or current is None:
        set_status(conflict, CURRENT)
        if current is not None:
            set_status(current, SUPERSEDED)
            session.add(current)
        kept = conflict
    else:
        set_status(conflict, SUPERSEDED)
        kept = current
    session.add(conflict)
    return kept
