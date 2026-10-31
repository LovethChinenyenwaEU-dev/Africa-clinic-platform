import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.interop.service import (
    ExportReason,
    NoSharingConsentError,
    PatientNotFoundError,
    export_patient,
)

router = APIRouter(prefix="/interop", tags=["interop"])


@router.get(
    "/patients/{patient_id}/fhir",
    dependencies=[Depends(require(Capability.RECORD_EXPORT))],
)
def export_patient_record(
    patient_id: uuid.UUID,
    reason: ExportReason,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """The patient's record as a FHIR R4 bundle (JSON). Doctors and nurses only.

    reason: patient_request (their own copy), referral or transfer (both need the
    patient's referral-sharing consent, else 409). Every export is in the audit log.
    """
    try:
        return export_patient(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
            reason=reason,
        )
    except PatientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from None
    except NoSharingConsentError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
