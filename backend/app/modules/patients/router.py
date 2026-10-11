import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.patients.phone import InvalidPhoneError
from app.modules.patients.schemas import PatientCreate, PatientResponse
from app.modules.patients.service import (
    InvalidPatientError,
    PossibleDuplicateError,
    create_patient,
    get_patient,
    search_patients,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.PATIENT_WRITE))],
)
def register_patient(
    body: PatientCreate,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Register a patient in the logged-in person's own clinic."""
    try:
        return create_patient(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            full_name=body.full_name,
            date_of_birth=body.date_of_birth,
            sex=body.sex,
            phone=body.phone,
            confirmed_not_duplicate=body.confirmed_not_duplicate,
        )
    except PossibleDuplicateError as warning:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This patient may already be registered.",
                "matches": [
                    {"patient_id": str(match.patient_id), "reason": match.reason}
                    for match in warning.matches
                ],
                "hint": "Check these patients, then send the form again with "
                "confirmed_not_duplicate set to true.",
            },
        ) from None
    except (InvalidPatientError, InvalidPhoneError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from None


@router.get(
    "",
    response_model=list[PatientResponse],
    dependencies=[Depends(require(Capability.PATIENT_READ))],
)
def search_my_patients(
    current_staff: CurrentStaff,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    session: Session = Depends(get_session),
):
    """Search this clinic's patients by part of a name or a phone number."""
    try:
        return search_patients(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            query=q,
        )
    except InvalidPatientError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from None


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    dependencies=[Depends(require(Capability.PATIENT_READ))],
)
def read_patient(
    patient_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """One patient, if they belong to the logged-in person's clinic."""
    patient = get_patient(
        session,
        tenant_id=current_staff.tenant_id,
        actor_id=current_staff.id,
        patient_id=patient_id,
    )
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient