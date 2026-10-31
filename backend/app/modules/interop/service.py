"""Export one patient's record as a FHIR R4 bundle (Week 11 Step 6, FR-I1).

What goes in: the patient, the clinic, the staff named in the record (names only), every
encounter, the vital signs, allergies, conditions and prescriptions in their current
version, and every consent (revoked ones too, marked inactive). Mistakes are not hidden:
an entry made in error is exported marked "entered-in-error", as FHIR expects.
Not included: clinical notes (the most sensitive text, not in FR-I1), follow-ups,
referrals, summaries, billing.

Why it is exported decides what it needs:
- patient_request: the patient asked for a copy of their own record (their right under
  the NDPA). No further consent needed;
- referral or transfer: the record goes to another provider. The patient must have an
  active "referral_sharing" consent.

Clinicians only (doctors and nurses, who can read the record). Every export is written
in the audit log with its reason.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.consent.models import Consent, ConsentPurpose, ConsentText
from app.modules.consent.service import has_active_consent
from app.modules.identity.models import Staff
from app.modules.interop import fhir
from app.modules.patients.models import Patient
from app.modules.records.models import Allergy, Encounter, Prescription, Problem, VitalSigns
from app.modules.records.statuses import VersionStatus
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import VisitType
from app.modules.tenancy.models import Tenant


class ExportReason(StrEnum):
    PATIENT_REQUEST = "patient_request"  # the patient's own copy
    REFERRAL = "referral"  # to the provider the patient is referred to
    TRANSFER = "transfer"  # the patient is moving to another provider


# Sending the record to another provider needs the patient's agreement to share it.
NEEDS_SHARING_CONSENT = frozenset({ExportReason.REFERRAL, ExportReason.TRANSFER})


class PatientNotFoundError(Exception):
    """No such patient in this clinic (another clinic's patient looks the same)."""


class NoSharingConsentError(Exception):
    """The patient has not agreed to their record being shared with another provider."""


def _rows(session: Session, model, tenant_id: uuid.UUID, patient_id: uuid.UUID, order) -> list:
    statement = (
        tenant_select(model, tenant_id)
        .where(col(model.patient_id) == patient_id)
        .order_by(col(order))
    )
    return list(session.exec(statement).all())


def _current(rows: list, field: str = "version_status") -> list:
    return [row for row in rows if getattr(row, field) == VersionStatus.CURRENT.value]


def export_patient(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    patient_id: uuid.UUID,
    reason: ExportReason,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The patient's record as a FHIR R4 collection bundle. Written in the audit log."""
    found = get_in_tenant(session, Patient, tenant_id=tenant_id, row_id=patient_id)
    if found is None:
        raise PatientNotFoundError(str(patient_id))
    if reason in NEEDS_SHARING_CONSENT and not has_active_consent(
        session,
        tenant_id=tenant_id,
        patient_id=patient_id,
        purpose=ConsentPurpose.REFERRAL_SHARING.value,
    ):
        raise NoSharingConsentError(
            "The patient has not agreed to share their record with another provider. "
            "Record their consent to referral sharing first."
        )
    tenant = session.get(Tenant, tenant_id)

    encounters = _rows(session, Encounter, tenant_id, patient_id, Encounter.opened_at)
    visits = _rows(session, Appointment, tenant_id, patient_id, Appointment.starts_at)
    remote = {v.id for v in visits if v.visit_type == VisitType.TELECONSULT.value}
    vitals = _current(
        _rows(session, VitalSigns, tenant_id, patient_id, VitalSigns.measured_at), "status"
    )
    allergies = _current(_rows(session, Allergy, tenant_id, patient_id, Allergy.recorded_at))
    problems = _current(_rows(session, Problem, tenant_id, patient_id, Problem.recorded_at))
    prescriptions = _current(
        _rows(session, Prescription, tenant_id, patient_id, Prescription.written_at)
    )
    consents = _rows(session, Consent, tenant_id, patient_id, Consent.granted_at)
    wording = {}
    text_ids = {c.consent_text_id for c in consents}
    if text_ids:
        texts = session.exec(
            tenant_select(ConsentText, tenant_id).where(col(ConsentText.id).in_(text_ids))
        ).all()
        wording = {text.id: text.version for text in texts}

    named = {e.clinician_id for e in encounters}
    for rows in (vitals, allergies, problems, prescriptions):
        named |= {row.recorded_by_id for row in rows}
    staff = [person for person in (session.get(Staff, i) for i in named) if person]
    staff = sorted(
        (person for person in staff if person.tenant_id == tenant_id),
        key=lambda person: person.full_name,
    )

    resources: list[dict[str, Any]] = [
        fhir.patient(found, tenant),
        fhir.organization(tenant),
        *(fhir.practitioner(person) for person in staff),
        *(fhir.encounter(e, remote=e.appointment_id in remote) for e in encounters),
    ]
    for row in vitals:
        resources.extend(fhir.vital_observations(row))
    resources += [fhir.allergy(row) for row in allergies]
    resources += [fhir.condition(row) for row in problems]
    resources += [fhir.medication_request(row) for row in prescriptions]
    resources += [
        fhir.consent(
            row, organization_id=tenant_id, wording_version=wording.get(row.consent_text_id)
        )
        for row in consents
    ]

    made_at = now or datetime.now(UTC)
    result = fhir.bundle(resources, bundle_id=uuid.uuid4(), made_at=made_at)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.RECORD_EXPORT,
        patient_id=patient_id,
        purpose=reason.value,
    )
    session.commit()
    return result
