"""
Test dates that count from today, so the tests never fall into the past.

Booking refuses times before "now", and the API uses the real clock, so a test
fixed on a calendar date starts failing the day after it. MONDAY is always a
Monday 8 to 14 days ahead: far enough that the Friday before it is still in the
future, and a Monday so the weekly hours in the tests still line up.

Tests of pure functions (message wording, status moves) may keep fixed dates.
"""

from datetime import UTC, date, datetime, time, timedelta

TODAY = datetime.now(UTC).date()
MONDAY: date = TODAY + timedelta(days=14 - TODAY.weekday())
FRIDAY_BEFORE: date = MONDAY - timedelta(days=3)


def utc(day: date, hour: int, minute: int = 0) -> datetime:
    """A UTC moment on the given day."""
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)
