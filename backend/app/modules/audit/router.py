import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.db import get_session
from app.modules.audit.schemas import AuditEventResponse
from app.modules.audit.service import MAX_AUDIT_PAGE, InvalidAuditFilterError, view_audit_log
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
    staff_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_AUDIT_PAGE)] = 50,
    session: Session = Depends(get_session),
):
    """The diary of the logged-in admin's own clinic, newest first. Reading it is logged.

    Filter by patient, by staff member, and by time: since (inclusive) and until
    (exclusive), both with a time zone, for example 2026-10-14T00:00:00+01:00.
    """
    try:
        return view_audit_log(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            patient_id=patient_id,
            staff_id=staff_id,
            since=since,
            until=until,
            limit=limit,
        )
    except InvalidAuditFilterError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
