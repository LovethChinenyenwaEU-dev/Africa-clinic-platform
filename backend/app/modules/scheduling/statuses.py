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