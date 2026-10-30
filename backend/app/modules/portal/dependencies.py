from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.db import get_session
from app.core.tenant_wall import raise_tenant_wall
from app.modules.identity.dependencies import bearer_scheme
from app.modules.identity.tokens import InvalidTokenError, decode_patient_token
from app.modules.patients.models import Patient


def get_current_patient(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> Patient:
    """The door guard of the patient pages: the signed-in patient, or 401.
    A staff token is refused here, as a patient token is refused on staff doors."""
    refused = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise refused
    try:
        claims = decode_patient_token(credentials.credentials)
    except InvalidTokenError:
        raise refused from None
    patient = session.get(Patient, claims.patient_id)
    if patient is None or patient.tenant_id != claims.tenant_id:
        raise refused
    # From here on the database itself only shows this clinic's rows (row-level security).
    raise_tenant_wall(session, patient.tenant_id)
    return patient


CurrentPatient = Annotated[Patient, Depends(get_current_patient)]
