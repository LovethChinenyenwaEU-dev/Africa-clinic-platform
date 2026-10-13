import uuid
from datetime import datetime, timedelta

import pytest

from app.modules.scheduling.lifecycle import (
    AppointmentNotFoundError,
    ClinicianMismatchError,
    cancel_appointment,
    check_in,
    complete_consultation,
    mark_no_show,
    reschedule_appointment,
    start_consultation,
)
from app.modules.scheduling.service import (
    ClinicianNotFoundError,
    InvalidAppointmentError,
    SlotTakenError,
)
from app.modules.scheduling.transitions import InvalidMoveError
from tests.scheduling_helpers import NOW, START, appointment_actions, book, build_clinic, walk_in


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def finish_visit(session, clinic, appointment):
    """Run a visit all the way through: check in, start, finish."""
    kwargs = {"appointment_id": appointment.id}
    check_in(session, now=START - timedelta(minutes=10), **kwargs, **who(clinic))
    start_consultation(session, now=START + timedelta(minutes=5), **kwargs, **who(clinic, "doctor"))
    return complete_consultation(
        session, now=START + timedelta(minutes=25), **kwargs, **who(clinic, "doctor")
    )


def test_check_in_makes_the_patient_wait_and_records_when(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)
    arrived = START - timedelta(minutes=10)

    result = check_in(session, appointment_id=appointment.id, now=arrived, **who(clinic))

    assert result.status == "waiting"
    assert result.checked_in_at == arrived
    assert appointment_actions(session, clinic) == ["appointment.check_in", "appointment.create"]


def test_a_full_visit_fills_in_the_stamps_and_the_diary(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)

    done = finish_visit(session, clinic, appointment)

    assert done.status == "done"
    assert done.checked_in_at == START - timedelta(minutes=10)
    assert done.consult_started_at == START + timedelta(minutes=5)
    assert done.completed_at == START + timedelta(minutes=25)
    assert done.consult_started_at - done.checked_in_at == timedelta(minutes=15)  # waiting time
    assert appointment_actions(session, clinic) == [
        "appointment.check_in",
        "appointment.complete",
        "appointment.create",
        "appointment.start",
    ]


def test_skipping_a_step_is_refused_and_nothing_changes(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)

    with pytest.raises(InvalidMoveError):
        start_consultation(
            session, appointment_id=appointment.id, now=START, **who(clinic, "doctor")
        )

    session.refresh(appointment)
    assert appointment.status == "booked"
    assert appointment.consult_started_at is None
    assert appointment_actions(session, clinic) == ["appointment.create"]


def test_a_finished_visit_cannot_be_reopened(session, clinics):
    clinic = clinics["a"]
    appointment = finish_visit(session, clinic, book(session, clinic))

    with pytest.raises(InvalidMoveError):
        check_in(session, appointment_id=appointment.id, now=START, **who(clinic))

    session.refresh(appointment)
    assert appointment.status == "done"


def test_cancelling_works_from_booked_and_waiting_and_frees_the_time(session, clinics):
    clinic = clinics["a"]
    first = book(session, clinic)
    assert cancel_appointment(session, appointment_id=first.id, **who(clinic)).status == "cancelled"

    again = book(session, clinic)  # the same slot is free again
    check_in(session, appointment_id=again.id, now=START, **who(clinic))
    cancelled = cancel_appointment(session, appointment_id=again.id, now=START, **who(clinic))

    assert cancelled.status == "cancelled"
    assert appointment_actions(session, clinic).count("appointment.cancel") == 2


def test_a_visit_in_progress_cannot_be_cancelled(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)
    kwargs = {"appointment_id": appointment.id, "now": START}
    check_in(session, **kwargs, **who(clinic))
    start_consultation(session, **kwargs, **who(clinic, "doctor"))

    with pytest.raises(InvalidMoveError):
        cancel_appointment(session, **kwargs, **who(clinic))

    session.refresh(appointment)
    assert appointment.status == "in_consult"


def test_no_show_is_only_allowed_after_the_start_time_and_frees_the_slot(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)

    with pytest.raises(InvalidMoveError):
        mark_no_show(
            session,
            appointment_id=appointment.id,
            now=START - timedelta(minutes=1),
            **who(clinic),
        )

    result = mark_no_show(
        session, appointment_id=appointment.id, now=START + timedelta(minutes=1), **who(clinic)
    )

    assert result.status == "no_show"
    assert "appointment.no_show" in appointment_actions(session, clinic)
    assert book(session, clinic).status == "booked"  # the slot is free again


def test_only_active_clinicians_can_run_a_consultation(session, clinics):
    clinic = clinics["a"]
    arrival = walk_in(session, clinic)

    with pytest.raises(ClinicianNotFoundError):
        start_consultation(session, appointment_id=arrival.id, now=NOW, **who(clinic, "desk"))

    session.refresh(arrival)
    assert arrival.status == "waiting"
    assert arrival.clinician_id is None


def test_starting_a_walk_in_assigns_the_clinician_who_starts_it(session, clinics):
    clinic = clinics["a"]
    arrival = walk_in(session, clinic)

    started = start_consultation(
        session,
        appointment_id=arrival.id,
        now=NOW + timedelta(minutes=5),
        **who(clinic, "nurse"),
    )

    assert started.status == "in_consult"
    assert started.clinician_id == clinic["nurse"].id
    assert started.consult_started_at == NOW + timedelta(minutes=5)


def test_another_clinician_cannot_take_over_or_finish_someone_elses_visit(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)  # booked with the doctor
    kwargs = {"appointment_id": appointment.id, "now": START}
    check_in(session, **kwargs, **who(clinic))

    with pytest.raises(ClinicianMismatchError):
        start_consultation(session, **kwargs, **who(clinic, "nurse"))
    start_consultation(session, **kwargs, **who(clinic, "doctor"))
    with pytest.raises(ClinicianMismatchError):
        complete_consultation(session, **kwargs, **who(clinic, "nurse"))

    session.refresh(appointment)
    assert appointment.status == "in_consult"
    assert appointment.clinician_id == clinic["doctor"].id


def test_another_clinics_appointment_looks_like_it_does_not_exist(session, clinics):
    a, b = clinics["a"], clinics["b"]
    appointment = book(session, a)

    for action in (
        check_in,
        start_consultation,
        complete_consultation,
        cancel_appointment,
        mark_no_show,
    ):
        with pytest.raises(AppointmentNotFoundError):
            action(session, appointment_id=appointment.id, now=START, **who(b, "doctor"))
        with pytest.raises(AppointmentNotFoundError):
            action(session, appointment_id=uuid.uuid4(), now=START, **who(b, "doctor"))
    with pytest.raises(AppointmentNotFoundError):
        reschedule_appointment(
            session,
            appointment_id=appointment.id,
            starts_at=START + timedelta(hours=3),
            now=NOW,
            **who(b),
        )

    session.refresh(appointment)
    assert appointment.status == "booked"
    assert appointment.starts_at == START
    assert appointment_actions(session, b) == []


def test_rescheduling_moves_the_visit_keeps_its_length_and_frees_the_old_time(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic, duration_minutes=45)
    new_start = START + timedelta(days=1)

    moved = reschedule_appointment(
        session, appointment_id=appointment.id, starts_at=new_start, now=NOW, **who(clinic)
    )

    assert moved.status == "booked"
    assert moved.starts_at == new_start
    assert moved.ends_at == new_start + timedelta(minutes=45)
    assert "appointment.reschedule" in appointment_actions(session, clinic)
    assert book(session, clinic).status == "booked"  # the old slot is free


def test_a_visit_can_shift_onto_part_of_its_own_old_time(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)

    moved = reschedule_appointment(
        session,
        appointment_id=appointment.id,
        starts_at=START + timedelta(minutes=15),
        now=NOW,
        **who(clinic),
    )

    assert moved.starts_at == START + timedelta(minutes=15)


def test_rescheduling_onto_another_visit_is_refused_and_nothing_moves(session, clinics):
    clinic = clinics["a"]
    book(session, clinic)
    other = book(session, clinic, starts_at=START + timedelta(hours=2))

    with pytest.raises(SlotTakenError):
        reschedule_appointment(
            session,
            appointment_id=other.id,
            starts_at=START + timedelta(minutes=10),
            now=NOW,
            **who(clinic),
        )

    session.refresh(other)
    assert other.starts_at == START + timedelta(hours=2)


@pytest.mark.parametrize(
    "changes",
    [
        {"starts_at": NOW - timedelta(minutes=1)},
        {"starts_at": datetime(2026, 11, 2, 12, 0)},  # no time zone
        {"duration_minutes": 1},
    ],
)
def test_bad_reschedules_are_refused_and_nothing_changes(session, clinics, changes):
    clinic = clinics["a"]
    appointment = book(session, clinic)
    values = {"starts_at": START + timedelta(hours=3)} | changes

    with pytest.raises(InvalidAppointmentError):
        reschedule_appointment(
            session, appointment_id=appointment.id, now=NOW, **values, **who(clinic)
        )

    session.refresh(appointment)
    assert appointment.starts_at == START
    assert appointment_actions(session, clinic) == ["appointment.create"]


def test_only_booked_visits_can_be_rescheduled(session, clinics):
    clinic = clinics["a"]
    appointment = book(session, clinic)
    check_in(session, appointment_id=appointment.id, now=START, **who(clinic))

    with pytest.raises(InvalidMoveError):
        reschedule_appointment(
            session,
            appointment_id=appointment.id,
            starts_at=START + timedelta(hours=3),
            now=NOW,
            **who(clinic),
        )