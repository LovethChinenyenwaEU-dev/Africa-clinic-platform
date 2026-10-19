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
    # Made from a version that was already replaced elsewhere (two devices, one offline).
    # Kept beside the current version until a clinician chooses (FR-O4).
    CONFLICT = "conflict"


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


class PrescriptionStatus(StrEnum):
    ACTIVE = "active"  # to be taken as written
    STOPPED = "stopped"  # a doctor stopped it (side effect, course changed)
    ENTERED_IN_ERROR = "entered_in_error"  # never meant: hidden from the list, kept


class MedicineRoute(StrEnum):
    """How the medicine is given. FHIR names it the route of administration."""

    ORAL = "oral"
    IV = "iv"  # into a vein
    IM = "im"  # into a muscle
    SC = "sc"  # under the skin
    TOPICAL = "topical"  # on the skin
    INHALED = "inhaled"
    RECTAL = "rectal"
    VAGINAL = "vaginal"
    EYE = "eye"
    EAR = "ear"
    NASAL = "nasal"
    OTHER = "other"


class FollowUpStatus(StrEnum):
    PLANNED = "planned"  # the clinician asked for it; front desk has not booked it yet
    BOOKED = "booked"  # a visit was booked for it
    CANCELLED = "cancelled"  # not needed after all, or the patient declined


class ReferralUrgency(StrEnum):
    ROUTINE = "routine"
    URGENT = "urgent"  # within days
    EMERGENCY = "emergency"  # now: the patient goes straight there


class ReferralStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"  # written by mistake, or no longer needed; kept


class SummaryStatus(StrEnum):
    DRAFT = "draft"  # being written; only its author may change it; the patient never sees it
    APPROVED = "approved"  # the encounter's clinician approved it: frozen, the patient may read it
    WITHDRAWN = "withdrawn"  # approved, then found wrong: kept, hidden from the patient
