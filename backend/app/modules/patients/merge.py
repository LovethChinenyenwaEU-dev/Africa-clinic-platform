"""Merging a duplicate patient into the original (Week 11; moved here from Week 8).

After the review says an offline registration was someone already registered
(review_status "duplicate", duplicate_of_id = the original), staff can merge it: every
visit, record, consent, invoice and message made under the duplicate moves to the
original, in one transaction, so the patient has one history.

What does not happen:
- nothing is deleted: the duplicate record stays, marked "merged", pointing at the
  original, so old links and printouts still lead somewhere;
- the audit log is never rewritten (it cannot be: the database refuses). Its old lines
  keep the duplicate's id, and the merge itself is written on both records, so an
  investigation of either one finds it;
- unused SMS sign-in codes for the duplicate are the one exception: they are thrown
  away, because a code sent to the duplicate's phone must not open the original.

Which tables move is read from the models (every clinic table with a patient_id), so a
table added later moves too without anyone remembering this file.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, update
from sqlmodel import Session, SQLModel, col

import app.model_registry  # noqa: F401  (every table must be known, to move them all)
from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.patients.models import Patient, ReviewStatus
from app.modules.portal.models import PatientLoginCode

# Never moved: the audit log is append-only; sign-in codes are thrown away instead.
NOT_MOVED = frozenset({"audit_event", "patient_login_code"})


class NotADuplicateError(Exception):
    """Only a record the review found to be a duplicate can be merged."""


class MergeTargetError(Exception):
    """The original cannot take the records (missing, or itself a duplicate)."""


@dataclass(frozen=True)
class MergeResult:
    original: Patient
    duplicate: Patient
    moved: dict[str, int]  # table name -> rows moved (tables with none are left out)


def tables_with_patients() -> list:
    """Every clinic table that points at a patient, from the models themselves."""
    return [
        table
        for table in SQLModel.metadata.sorted_tables
        if "patient_id" in table.c
        and "tenant_id" in table.c
        and table.name not in NOT_MOVED
    ]


def _locked(session: Session, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> Patient | None:
    statement = (
        tenant_select(Patient, tenant_id).where(col(Patient.id) == patient_id).with_for_update()
    )
    return session.exec(statement).first()


def merge_duplicate(
    session: Session, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, duplicate_id: uuid.UUID
) -> MergeResult:
    """Move everything from the duplicate to its original. All or nothing."""
    duplicate = _locked(session, tenant_id, duplicate_id)
    if duplicate is None:
        raise LookupError("Patient not found.")
    if duplicate.review_status != ReviewStatus.DUPLICATE.value or not duplicate.duplicate_of_id:
        raise NotADuplicateError(
            "Only a record the review found to be a duplicate can be merged."
        )
    original = _locked(session, tenant_id, duplicate.duplicate_of_id)
    if original is None:
        raise MergeTargetError("The original record was not found.")
    if original.review_status in (ReviewStatus.DUPLICATE.value, ReviewStatus.MERGED.value):
        raise MergeTargetError(
            "The original is itself a duplicate. Merge it into its own original first."
        )

    moved: dict[str, int] = {}
    for table in tables_with_patients():
        result = session.execute(
            update(table)
            .where(table.c.tenant_id == tenant_id)
            .where(table.c.patient_id == duplicate.id)
            .values(patient_id=original.id)
        )
        if result.rowcount:
            moved[table.name] = result.rowcount
    session.execute(
        delete(PatientLoginCode)
        .where(col(PatientLoginCode.tenant_id) == tenant_id)
        .where(col(PatientLoginCode.patient_id) == duplicate.id)
    )
    # Records found earlier to duplicate this one now point straight at the original.
    session.execute(
        update(Patient)
        .where(col(Patient.tenant_id) == tenant_id)
        .where(col(Patient.duplicate_of_id) == duplicate.id)
        .values(duplicate_of_id=original.id)
    )

    duplicate.review_status = ReviewStatus.MERGED.value
    session.add(duplicate)
    for patient_id, other_id in ((original.id, duplicate.id), (duplicate.id, original.id)):
        add_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=AuditAction.PATIENT_MERGE,
            patient_id=patient_id,
            entity_id=other_id,
        )
    session.commit()
    session.refresh(original)
    session.refresh(duplicate)
    return MergeResult(original=original, duplicate=duplicate, moved=moved)
