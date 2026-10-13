from enum import StrEnum


class EncounterStatus(StrEnum):
    OPEN = "open"  # the clinician is still recording
    CLOSED = "closed"  # signed off; changes from now on are new versions, never edits
    ENTERED_IN_ERROR = "entered_in_error"  # opened by mistake; kept, never deleted


# The only moves allowed. A closed encounter is final; mistakes are marked, not removed.
ALLOWED_MOVES: dict[EncounterStatus, frozenset[EncounterStatus]] = {
    EncounterStatus.OPEN: frozenset({EncounterStatus.CLOSED, EncounterStatus.ENTERED_IN_ERROR}),
    EncounterStatus.CLOSED: frozenset(),
    EncounterStatus.ENTERED_IN_ERROR: frozenset(),
}


class VitalsStatus(StrEnum):
    CURRENT = "current"  # the version to use
    SUPERSEDED = "superseded"  # replaced by a correction; kept forever, numbers never changed
