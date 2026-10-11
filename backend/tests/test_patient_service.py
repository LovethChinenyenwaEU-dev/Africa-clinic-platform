from datetime import date

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.identity.service import create_staff
from app.modules.patients.models import Patient
from app.modules.patients.service import (
    DuplicateMatch,
    InvalidPatientError,
    PossibleDuplicateError,
    create_patient,
    get_patient,
    search_patients,
)
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"


@pytest.fixture
def clinics(session, run_id):
    """Two separate clinics, each with a front desk person."""
    data = {}
    for label in ("a", "b"):
        tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
        staff = create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{label}@{run_id}.example.com",
            full_name=f"Desk {label}",
            role="front_desk",
            password=PASSWORD,
        )
        data[label] = {"tenant": tenant, "staff": staff}
    return data


def register(
    session,
    clinic,
    *,
    name="Test Patient Alpha",
    dob=date(1990, 5, 17),
    sex="female",
    phone=None,
    confirmed=False,
):
    return create_patient(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["staff"].id,
        full_name=name,
        date_of_birth=dob,
        sex=sex,
        phone=phone,
        confirmed_not_duplicate=confirmed,
    )


def stored_patients(session, clinic):
    return session.exec(tenant_select(Patient, clinic["tenant"].id)).all()


def test_create_tidies_details_and_writes_a_diary_line(session, clinics):
    clinic = clinics["a"]
    patient = register(session, clinic, name="  Test   Patient  Alpha ", phone="0803 123 4567")

    assert patient.full_name == "Test Patient Alpha"
    assert patient.phone == "+2348031234567"
    assert patient.created_by_id == clinic["staff"].id

    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    assert [(e.action, e.patient_id, e.actor_id) for e in events] == [
        ("patient.create", patient.id, clinic["staff"].id)
    ]


def test_same_phone_gives_a_warning_and_creates_nothing(session, clinics):
    clinic = clinics["a"]
    first = register(session, clinic, phone="08031234567")

    with pytest.raises(PossibleDuplicateError) as warning:
        register(session, clinic, name="Test Patient Beta", dob=date(2001, 1, 1),
                 phone="+234 803 123 4567")

    assert warning.value.matches == [DuplicateMatch(patient_id=first.id, reason="same_phone")]
    assert [p.full_name for p in stored_patients(session, clinic)] == ["Test Patient Alpha"]
    assert len(list_audit_events(session, tenant_id=clinic["tenant"].id)) == 1


def test_same_name_and_birth_date_gives_a_warning_ignoring_capitals(session, clinics):
    clinic = clinics["a"]
    first = register(session, clinic, name="Test Patient Alpha", dob=date(1990, 5, 17))

    with pytest.raises(PossibleDuplicateError) as warning:
        register(session, clinic, name="  test patient ALPHA ", dob=date(1990, 5, 17))

    assert warning.value.matches == [
        DuplicateMatch(patient_id=first.id, reason="same_name_and_birth_date")
    ]


def test_a_human_can_confirm_it_is_a_different_person(session, clinics):
    clinic = clinics["a"]
    register(session, clinic, phone="08031234567")

    sibling = register(
        session,
        clinic,
        name="Test Patient Beta",
        dob=date(2012, 3, 4),
        phone="08031234567",
        confirmed=True,
    )

    assert sibling.phone == "+2348031234567"
    assert len(stored_patients(session, clinic)) == 2


def test_duplicates_are_only_looked_for_inside_the_same_clinic(session, clinics):
    register(session, clinics["a"], phone="08031234567")
    other = register(session, clinics["b"], phone="08031234567")
    assert other.tenant_id == clinics["b"]["tenant"].id


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "   "},
        {"dob": date(2999, 1, 1)},
        {"dob": date(1800, 1, 1)},
        {"sex": "robot"},
        {"phone": "12345"},
    ],
)
def test_bad_details_are_refused_and_nothing_is_saved(session, clinics, changes):
    clinic = clinics["a"]
    with pytest.raises(ValueError):
        register(session, clinic, **changes)

    assert stored_patients(session, clinic) == []
    assert list_audit_events(session, tenant_id=clinic["tenant"].id) == []


def test_viewing_a_patient_writes_a_diary_line(session, clinics):
    clinic = clinics["a"]
    patient = register(session, clinic)

    seen = get_patient(
        session,
        tenant_id=clinic["tenant"].id,
        actor_id=clinic["staff"].id,
        patient_id=patient.id,
    )

    assert seen is not None and seen.id == patient.id
    events = list_audit_events(session, tenant_id=clinic["tenant"].id, patient_id=patient.id)
    assert sorted(event.action for event in events) == ["patient.create", "patient.view"]


def test_another_clinics_patient_cannot_be_viewed_and_leaves_no_line(session, clinics):
    patient = register(session, clinics["a"])
    snooper = clinics["b"]

    seen = get_patient(
        session,
        tenant_id=snooper["tenant"].id,
        actor_id=snooper["staff"].id,
        patient_id=patient.id,
    )

    assert seen is None
    assert list_audit_events(session, tenant_id=snooper["tenant"].id) == []


def test_search_finds_by_part_of_a_name_ignoring_capitals(session, clinics):
    clinic = clinics["a"]
    register(session, clinic, name="Test Patient Alpha")
    register(session, clinic, name="Test Patient Beta", dob=date(2001, 1, 1))

    found = search_patients(
        session, tenant_id=clinic["tenant"].id, actor_id=clinic["staff"].id, query="alph"
    )

    assert [patient.full_name for patient in found] == ["Test Patient Alpha"]


@pytest.mark.parametrize("typed", ["0803 123 4567", "+2348031234567", "2348031234567"])
def test_search_finds_by_phone_however_it_is_typed(session, clinics, typed):
    clinic = clinics["a"]
    patient = register(session, clinic, phone="08031234567")
    register(session, clinic, name="Test Patient Beta", dob=date(2001, 1, 1))

    found = search_patients(
        session, tenant_id=clinic["tenant"].id, actor_id=clinic["staff"].id, query=typed
    )

    assert [p.id for p in found] == [patient.id]


def test_search_stays_inside_the_clinic(session, clinics):
    register(session, clinics["a"], name="Test Patient Alpha")
    register(session, clinics["b"], name="Test Patient Alpha Two")

    found = search_patients(
        session,
        tenant_id=clinics["a"]["tenant"].id,
        actor_id=clinics["a"]["staff"].id,
        query="Test Patient",
    )

    assert {patient.full_name for patient in found} == {"Test Patient Alpha"}


def test_search_writes_a_diary_line_without_the_search_words(session, clinics):
    clinic = clinics["a"]
    register(session, clinic)

    search_patients(
        session, tenant_id=clinic["tenant"].id, actor_id=clinic["staff"].id, query="Alpha"
    )

    searches = [
        event
        for event in list_audit_events(session, tenant_id=clinic["tenant"].id)
        if event.action == "patient.search"
    ]
    assert len(searches) == 1
    assert searches[0].patient_id is None


def test_short_and_wildcard_searches_do_not_list_everyone(session, clinics):
    clinic = clinics["a"]
    register(session, clinic, name="Test Patient Alpha")
    register(session, clinic, name="Test Patient Beta", dob=date(2001, 1, 1))
    who = {"tenant_id": clinic["tenant"].id, "actor_id": clinic["staff"].id}

    with pytest.raises(InvalidPatientError):
        search_patients(session, query="a", **who)

    assert search_patients(session, query="%%", **who) == []