import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.consent.schemas import (
    ConsentCreate,
    ConsentResponse,
    ConsentTextCreate,
    ConsentTextResponse,
)
from app.modules.consent.service import (
    ConsentNotFoundError,
    InvalidConsentError,
    NoConsentTextError,
    current_consent_text,
    grant_consent,
    list_patient_consents,
    publish_consent_text,
    revoke_consent,
    summarise_consent,
)
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.patients.service import PatientNotFoundError

router = APIRouter(tags=["consent"])

PATIENT_NOT_FOUND = "Patient not found."


@router.post(
    "/consent/texts",
    response_model=ConsentTextResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.CONSENT_TEXT_WRITE))],
)
def publish_wording(
    body: ConsentTextCreate,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Publish new wording. It becomes the next version of this clinic's wording."""
    try:
        return publish_consent_text(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            purpose=body.purpose,
            body=body.body,
        )
    except InvalidConsentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get(
    "/consent/texts/current",
    response_model=ConsentTextResponse,
    dependencies=[Depends(require(Capability.CONSENT_TEXT_READ))],
)
def read_current_wording(
    current_staff: CurrentStaff,
    purpose: Annotated[str, Query(min_length=1, max_length=40)],
    session: Session = Depends(get_session),
):
    """The newest wording this clinic has published for a purpose."""
    try:
        text = current_consent_text(session, tenant_id=current_staff.tenant_id, purpose=purpose)
    except InvalidConsentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consent text has been published for this purpose.",
        )
    return text


@router.post(
    "/patients/{patient_id}/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.CONSENT_WRITE))],
)
def record_consent(
    patient_id: uuid.UUID,
    body: ConsentCreate,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Record that a patient agreed. Sending it twice returns the same consent."""
    try:
        consent = grant_consent(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
            purpose=body.purpose,
            granted_by=body.granted_by,
        )
    except InvalidConsentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except PatientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=PATIENT_NOT_FOUND
        ) from None
    except NoConsentTextError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return summarise_consent(session, tenant_id=current_staff.tenant_id, consent=consent)


@router.get(
    "/patients/{patient_id}/consents",
    response_model=list[ConsentResponse],
    dependencies=[Depends(require(Capability.CONSENT_READ))],
)
def read_consent_history(
    patient_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """A patient's consent history, newest first, including revoked ones."""
    try:
        return list_patient_consents(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
        )
    except PatientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=PATIENT_NOT_FOUND
        ) from None


@router.post(
    "/patients/{patient_id}/consents/{purpose}/revoke",
    response_model=ConsentResponse,
    dependencies=[Depends(require(Capability.CONSENT_WRITE))],
)
def revoke_patient_consent(
    patient_id: uuid.UUID,
    purpose: str,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Take permission back. The record stays, stamped with when it was revoked."""
    try:
        consent = revoke_consent(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
            purpose=purpose,
        )
    except InvalidConsentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except ConsentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active consent found."
        ) from None
    return summarise_consent(session, tenant_id=current_staff.tenant_id, consent=consent)