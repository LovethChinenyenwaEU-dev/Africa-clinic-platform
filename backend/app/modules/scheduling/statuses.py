from enum import StrEnum


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    WAITING = "waiting"
    IN_CONSULT = "in_consult"
    DONE = "done"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentKind(StrEnum):
    SCHEDULED = "scheduled"  # booked ahead
    WALK_IN = "walk_in"  # arrived without a booking


class VisitType(StrEnum):
    IN_PERSON = "in_person"
    TELECONSULT = "teleconsult"


# Statuses where the appointment still occupies the clinician's time.
ACTIVE_STATUSES = frozenset(
    {
        AppointmentStatus.BOOKED,
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULT,
    }
)

class TriageLevel(StrEnum):
    """How soon a waiting patient must be seen. The queue is ordered by this first."""

    EMERGENCY = "emergency"  # now: a red flag, or the nurse judges it so
    URGENT = "urgent"  # soon, ahead of routine visits
    STANDARD = "standard"  # in arrival order


# Lower is seen first.
TRIAGE_RANK = {TriageLevel.EMERGENCY: 0, TriageLevel.URGENT: 1, TriageLevel.STANDARD: 2}
UNTRIAGED_RANK = TRIAGE_RANK[TriageLevel.STANDARD]  # not yet triaged: in arrival order


class RedFlag(StrEnum):
    """Danger signs that mean "see a clinician now, in person". Codes only, never free text.

    Based on general danger signs (WHO IMCI for children, emergency triage for adults).
    The same list screens teleconsult intake (Week 9), where any of them sends the
    patient to in-person care.
    """

    DIFFICULTY_BREATHING = "difficulty_breathing"
    CHEST_PAIN = "chest_pain"
    UNCONSCIOUS_OR_CONFUSED = "unconscious_or_confused"
    CONVULSIONS = "convulsions"
    SEVERE_BLEEDING = "severe_bleeding"
    STROKE_SIGNS = "stroke_signs"  # face drooping, arm weakness, speech trouble
    SEVERE_DEHYDRATION = "severe_dehydration"
    FEVER_WITH_STIFF_NECK = "fever_with_stiff_neck"
    PREGNANCY_BLEEDING_OR_PAIN = "pregnancy_bleeding_or_pain"
    CHILD_UNABLE_TO_DRINK = "child_unable_to_drink"
    SEVERE_PAIN = "severe_pain"
    THOUGHTS_OF_SELF_HARM = "thoughts_of_self_harm"
