from datetime import UTC, datetime, timedelta

import pytest

from app.modules.scheduling.statuses import AppointmentStatus as Status
from app.modules.scheduling.transitions import ALLOWED_MOVES, InvalidMoveError, check_move

START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
LATER = START + timedelta(hours=1)

# The decision, written out once: these six moves and no others.
ALLOWED_PAIRS = {
    (Status.BOOKED, Status.WAITING),
    (Status.BOOKED, Status.CANCELLED),
    (Status.BOOKED, Status.NO_SHOW),
    (Status.WAITING, Status.IN_CONSULT),
    (Status.WAITING, Status.CANCELLED),
    (Status.IN_CONSULT, Status.DONE),
}


def test_every_status_has_an_entry_in_the_map():
    assert set(ALLOWED_MOVES) == set(Status)


@pytest.mark.parametrize("current", list(Status))
@pytest.mark.parametrize("target", list(Status))
def test_exactly_the_agreed_moves_are_allowed(current, target):
    if (current, target) in ALLOWED_PAIRS:
        assert check_move(current.value, target.value, starts_at=START, now=LATER) is target
    else:
        with pytest.raises(InvalidMoveError):
            check_move(current.value, target.value, starts_at=START, now=LATER)


def test_a_normal_visit_goes_booked_waiting_in_consult_done():
    path = [Status.BOOKED, Status.WAITING, Status.IN_CONSULT, Status.DONE]
    for current, target in zip(path, path[1:]):
        assert check_move(current.value, target.value, starts_at=START, now=LATER) is target


def test_no_show_is_refused_before_the_start_time():
    just_before = START - timedelta(minutes=1)
    with pytest.raises(InvalidMoveError):
        check_move("booked", "no_show", starts_at=START, now=just_before)


def test_no_show_is_allowed_from_the_start_time_on():
    assert check_move("booked", "no_show", starts_at=START, now=START) is Status.NO_SHOW


def test_unknown_statuses_are_refused():
    with pytest.raises(InvalidMoveError):
        check_move("wizard", "done", starts_at=START, now=LATER)
    with pytest.raises(InvalidMoveError):
        check_move("booked", "wizard", starts_at=START, now=LATER)