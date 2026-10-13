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


class VersionStatus(StrEnum):
    CURRENT = "current"  # the version to use
    SUPERSEDED = "superseded"  # replaced by a newer version; kept forever, never changed


class AllergyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"  # no longer a concern, for example outgrown
    ENTERED_IN_ERROR = "entered_in_error"


class AllergySeverity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class ProblemStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ENTERED_IN_ERROR = "entered_in_error"


class ProblemCategory(StrEnum):
    PROBLEM_LIST = "problem_list"  # an ongoing condition, like hypertension
    ENCOUNTER_DIAGNOSIS = "encounter_diagnosis"  # what this visit was for, like malaria


class NoteKind(StrEnum):
    HISTORY = "history"  # what the patient reports
    EXAMINATION = "examination"  # what the clinician finds
    ASSESSMENT = "assessment"  # what the clinician thinks is going on
    PLAN = "plan"  # what happens next
    PROGRESS = "progress"  # how things are going since last time
