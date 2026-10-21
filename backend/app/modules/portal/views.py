"""What a signed-in patient sees of their own record: visits and approved summaries."""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.identity.service import get_staff_in_tenant
from app.modules.patients.models import Patient
from app.modules.portal.signin import PORTAL
from app.modules.records.models import PatientSummary
from app.modules.records.summary import approved_summaries_for_patient
from app.modules.scheduling.models import Appointment

PAST_DAYS_SHOWN = 180


@dataclass(frozen=True)
class MyVisit:
    appointment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    visit_type: str
    status: str
    clinician_name: str | None


def _clinician_name(
    session: Session, tenant_id: uuid.UUID, staff_id: uuid.UUID | None
) -> str | None:
    if staff_id is None:
        return None
    staff = get_staff_in_tenant(session, tenant_id=tenant_id, staff_id=staff_id)
    return staff.full_name if staff else None


def _note_look(session: Session, patient: Patient, action: AuditAction) -> None:
    add_audit_event(
        session,
        tenant_id=patient.tenant_id,
        actor_id=patient.id,  # the patient is the actor on their own pages
        action=action,
        patient_id=patient.id,
        purpose=PORTAL,
    )
    session.commit()


def my_visits(session: Session, *, patient: Patient, now: datetime | None = None) -> list[MyVisit]:
    """Upcoming visits first (soonest first), then the last six months (newest first)."""
    current = now or datetime.now(UTC)
    _note_look(session, patient, AuditAction.PORTAL_VISITS_VIEW)
    rows = session.exec(
        tenant_select(Appointment, patient.tenant_id)
        .where(col(Appointment.patient_id) == patient.id)
        .where(col(Appointment.starts_at) >= current - timedelta(days=PAST_DAYS_SHOWN))
    ).all()
    upcoming = sorted((row for row in rows if row.ends_at >= current), key=lambda r: r.starts_at)
    past = sorted(
        (row for row in rows if row.ends_at < current), key=lambda r: r.starts_at, reverse=True
    )
    names: dict[uuid.UUID | None, str | None] = {}
    visits = []
    for row in upcoming + past:
        if row.clinician_id not in names:
            names[row.clinician_id] = _clinician_name(session, patient.tenant_id, row.clinician_id)
        visits.append(
            MyVisit(
                appointment_id=row.id,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                visit_type=row.visit_type,
                status=row.status,
                clinician_name=names[row.clinician_id],
            )
        )
    return visits


def my_summaries(session: Session, *, patient: Patient) -> list[PatientSummary]:
    """Approved summaries only, newest first. Drafts and withdrawn ones never show."""
    _note_look(session, patient, AuditAction.PORTAL_SUMMARIES_VIEW)
    return approved_summaries_for_patient(
        session, tenant_id=patient.tenant_id, patient_id=patient.id
    )
