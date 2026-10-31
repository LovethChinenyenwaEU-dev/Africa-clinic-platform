from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.reports.dashboard import BadRangeError, clinic_dashboard
from app.modules.reports.schemas import DashboardResponse
from app.modules.scheduling.board import lagos_day

router = APIRouter(prefix="/reports", tags=["reports"])

DEFAULT_DAYS = 7


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    dependencies=[Depends(require(Capability.REPORT_READ))],
)
def read_dashboard(
    current_staff: CurrentStaff,
    from_day: date | None = None,
    to_day: date | None = None,
    session: Session = Depends(get_session),
):
    """The clinic's numbers for these Lagos days (both included). The last 7 days, up to
    today, when no days are given. Admins only; no patient details."""
    last = to_day or lagos_day(datetime.now(UTC))
    first = from_day or last - timedelta(days=DEFAULT_DAYS - 1)
    try:
        result = clinic_dashboard(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            from_day=first,
            to_day=last,
        )
    except BadRangeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return DashboardResponse.model_validate(result)
