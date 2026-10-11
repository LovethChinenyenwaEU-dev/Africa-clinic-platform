import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.db import get_session
from app.modules.audit.schemas import AuditEventResponse
from app.modules.audit.service import MAX_AUDIT_PAGE, view_audit_log
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/events",
    response_model=list[AuditEventResponse],
    dependencies=[Depends(require(Capability.AUDIT_READ))],
)
def read_audit_events(
    current_staff: CurrentStaff,
    patient_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_AUDIT_PAGE)] = 50,
    session: Session = Depends(get_session),
):
    """The diary of the logged-in admin's own clinic, newest first. Reading it is logged."""
    return view_audit_log(
        session,
        tenant_id=current_staff.tenant_id,
        actor_id=current_staff.id,
        patient_id=patient_id,
        limit=limit,
    )