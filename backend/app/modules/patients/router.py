import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.patients.phone import InvalidPhoneError
from app.modules.patients.schemas import (
    PatientCreate,
    PatientResponse,
    ReviewDecision,
    ReviewItemResponse,
    ReviewMatch,
)
from app.modules.patients.service import (
    InvalidPatientError,
    NotWaitingForReviewError,
    PatientNotFoundError,
    PossibleDuplicateError,
    create_patient,
    get_patient,
    list_for_review,
    review_patient,
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
            patient_id=body.id,
            registered_offline=body.registered_offline,
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


# Declared before "/{patient_id}" so the word is never read as a patient ID.
@router.get(
    "/review-queue",
    response_model=list[ReviewItemResponse],
    dependencies=[Depends(require(Capability.PATIENT_WRITE))],
)
def registrations_to_review(current_staff: CurrentStaff, session: Session = Depends(get_session)):
    """Offline registrations that may be someone already registered, waiting for a decision."""
    items = list_for_review(session, tenant_id=current_staff.tenant_id, actor_id=current_staff.id)
    return [
        ReviewItemResponse(
            patient=PatientResponse.model_validate(item.patient),
            matches=[
                ReviewMatch(patient=PatientResponse.model_validate(match), reason=reason)
                for match, reason in item.matches
            ],
        )
        for item in items
    ]


@router.post(
    "/{patient_id}/review",
    response_model=PatientResponse,
    dependencies=[Depends(require(Capability.PATIENT_WRITE))],
)
def decide_review(
    patient_id: uuid.UUID,
    body: ReviewDecision,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Someone new, or already registered as `duplicate_of`. Nothing is merged or deleted."""
    try:
        return review_patient(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
            duplicate_of=body.duplicate_of,
        )
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found.") from None
    except NotWaitingForReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except InvalidPatientError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


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