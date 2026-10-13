from datetime import datetime

from app.modules.scheduling.statuses import AppointmentStatus as Status

# The map: from each status, where it may go next. Nothing else is allowed.
ALLOWED_MOVES: dict[Status, frozenset[Status]] = {
    Status.BOOKED: frozenset({Status.WAITING, Status.CANCELLED, Status.NO_SHOW}),
    Status.WAITING: frozenset({Status.IN_CONSULT, Status.CANCELLED}),
    Status.IN_CONSULT: frozenset({Status.DONE}),
    Status.DONE: frozenset(),
    Status.CANCELLED: frozenset(),
    Status.NO_SHOW: frozenset(),
}


class InvalidMoveError(Exception):
    """The appointment cannot move from its current status to that one."""


def check_move(current: str, target: str, *, starts_at: datetime, now: datetime) -> Status:
    """Return the new status if the move is allowed. Otherwise raise InvalidMoveError."""
    try:
        current_status = Status(current)
        target_status = Status(target)
    except ValueError:
        raise InvalidMoveError("Unknown appointment status.") from None

    if target_status not in ALLOWED_MOVES[current_status]:
        raise InvalidMoveError(
            f"An appointment that is {current_status.value} cannot become {target_status.value}."
        )
    if target_status is Status.NO_SHOW and now < starts_at:
        raise InvalidMoveError("An appointment cannot be a no-show before its start time.")
    return target_status