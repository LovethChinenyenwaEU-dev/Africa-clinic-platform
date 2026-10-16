"""Late offline entries: taken before sign-off, synced after it (Week 8 decision).

A nurse takes vitals on a tablet with no network; meanwhile the doctor signs off on
another device. When the tablet reconnects, refusing the vitals would lose a real
measurement. So an entry is accepted into a signed-off encounter when the device
says it was taken while the encounter was open, and it is marked `synced_late` so
the doctor can see it arrived after they signed.

What is never accepted: an entry with no device time (it was made now, after
sign-off), one dated after sign-off, or one dated before the encounter began.
"""
from datetime import datetime, timedelta

from app.modules.records.models import Encounter
from app.modules.records.service import EncounterNotOpenError
from app.modules.records.statuses import EncounterStatus

# A device clock may run a little ahead of, or behind, the server.
CLOCK_SKEW = timedelta(minutes=5)


def is_late_entry(encounter: Encounter, *, taken_at: datetime | None, refusal: str) -> bool:
    """False if the encounter is open. True if it is closed but the entry was taken
    while it was open. Otherwise raises EncounterNotOpenError with `refusal`."""
    if encounter.status == EncounterStatus.OPEN.value:
        return False
    if (
        encounter.status == EncounterStatus.CLOSED.value
        and taken_at is not None
        and encounter.closed_at is not None
        and encounter.opened_at - CLOCK_SKEW <= taken_at <= encounter.closed_at
    ):
        return True
    raise EncounterNotOpenError(refusal)
