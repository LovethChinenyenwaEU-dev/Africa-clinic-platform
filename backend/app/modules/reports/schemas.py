import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class _FromObject(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VisitsResponse(_FromObject):
    total: int
    walk_ins: int
    done: int
    no_shows: int
    cancelled: int
    still_open: int
    checked_in: int
    no_show_rate: float | None  # 0 to 1; None when nobody was due
    completion_rate: float | None  # 0 to 1; None when nobody checked in


class WaitsResponse(_FromObject):
    measured: int
    median_minutes: float | None
    p90_minutes: float | None
    over_an_hour: int


class MethodTotalResponse(_FromObject):
    method: str
    count: int
    amount_kobo: int


class RevenueResponse(_FromObject):
    invoices_issued: int
    billed_kobo: int
    payments: int
    received_kobo: int
    refunds: int
    refunded_kobo: int
    net_kobo: int
    by_method: list[MethodTotalResponse]


class SyncResponse(_FromObject):
    late_entries: int
    open_conflicts: int
    registrations_to_review: int
    reminders_sent: int
    reminders_failed: int
    online_payments_failed: int


class StaffAccessResponse(_FromObject):
    staff_id: uuid.UUID
    name: str
    events: int
    patients: int


class RecordAccessResponse(_FromObject):
    events: int
    patients: int
    by_staff: list[StaffAccessResponse]


class DayResponse(_FromObject):
    day: date
    visits: int
    done: int
    no_shows: int
    median_wait_minutes: float | None
    received_kobo: int


class DashboardResponse(_FromObject):
    """The clinic's numbers for some days. Counts and sums only: no patient details."""

    from_day: date
    to_day: date
    visits: VisitsResponse
    waits: WaitsResponse
    revenue: RevenueResponse
    sync: SyncResponse
    record_access: RecordAccessResponse
    days: list[DayResponse]
