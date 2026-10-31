import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.notifications.console import (
    BadRangeError,
    CannotRetryError,
    ReminderNotFoundError,
    reminder_console,
    retry_reminder,
)
from app.modules.notifications.schemas import (
    ReminderConsoleResponse,
    ReminderLineResponse,
    ReminderRetriedResponse,
)
from app.modules.notifications.statuses import ReminderStatus
from app.modules.scheduling.board import lagos_day

router = APIRouter(prefix="/notifications", tags=["notifications"])

MANAGE = [Depends(require(Capability.NOTIFICATIONS_MANAGE))]  # admins only
DEFAULT_DAYS = 7


@router.get("/reminders", response_model=ReminderConsoleResponse, dependencies=MANAGE)
def read_reminders(
    current_staff: CurrentStaff,
    from_day: date | None = None,
    to_day: date | None = None,
    reminder_status: ReminderStatus | None = None,
    session: Session = Depends(get_session),
):
    """Reminders due in these Lagos days (the last 7 by default, at most 31), with counts
    by status and by reason for failing. Optionally only one status."""
    now = datetime.now(UTC)
    last = to_day or lagos_day(now)
    first = from_day or last - timedelta(days=DEFAULT_DAYS - 1)
    try:
        console = reminder_console(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            from_day=first,
            to_day=last,
            status=reminder_status,
            now=now,
        )
    except BadRangeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return ReminderConsoleResponse(
        from_day=console.from_day,
        to_day=console.to_day,
        counts=console.counts,
        failures=console.failures,
        more=console.more,
        lines=[
            ReminderLineResponse(
                id=line.reminder.id,
                appointment_id=line.reminder.appointment_id,
                channel=line.reminder.channel,
                status=line.reminder.status,
                due_at=line.reminder.due_at,
                attempts=line.reminder.attempts,
                last_error=line.reminder.last_error,
                sent_at=line.reminder.sent_at,
                visit_starts_at=line.visit_starts_at,
                visit_type=line.visit_type,
                can_retry=line.can_retry,
            )
            for line in console.lines
        ],
    )


@router.post(
    "/reminders/{reminder_id}/retry", response_model=ReminderRetriedResponse, dependencies=MANAGE
)
def retry_one_reminder(
    reminder_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Put a failed reminder back in the queue (its visit must still be booked and ahead)."""
    try:
        reminder = retry_reminder(
            session,
            tenant_id=current_staff.tenant_id,
            actor_id=current_staff.id,
            reminder_id=reminder_id,
            now=datetime.now(UTC),
        )
    except ReminderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from None
    except CannotRetryError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return ReminderRetriedResponse(id=reminder.id, status=reminder.status, due_at=reminder.due_at)
