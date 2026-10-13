import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.tenant_scope import tenant_select
from app.modules.records.models import Encounter
from tests.scheduling_helpers import build_clinic, walk_in


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "e")


def make_encounter(clinic, **changes):
    values = {
        "tenant_id": clinic["tenant"].id,
        "patient_id": clinic["patient"].id,
        "clinician_id": clinic["doctor"].id,
        "status": "open",
    }
    return Encounter(**(values | changes))


def stored(session, clinic):
    return session.exec(tenant_select(Encounter, clinic["tenant"].id)).all()


def test_encounter_roundtrip_starts_open_and_unsigned(session, clinic):
    visit = walk_in(session, clinic)
    session.add(make_encounter(clinic, appointment_id=visit.id))
    session.commit()

    (saved,) = stored(session, clinic)

    assert saved.status == "open"
    assert saved.appointment_id == visit.id
    assert saved.opened_at is not None
    assert saved.closed_at is None
    assert saved.closed_by_id is None


def test_an_id_made_on_the_device_is_kept(session, clinic):
    device_id = uuid.uuid4()
    session.add(make_encounter(clinic, id=device_id))
    session.commit()

    (saved,) = stored(session, clinic)

    assert saved.id == device_id


def test_one_visit_cannot_have_two_encounters(session, clinic):
    visit = walk_in(session, clinic)
    session.add(make_encounter(clinic, appointment_id=visit.id))
    session.commit()

    session.add(make_encounter(clinic, appointment_id=visit.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_encounters_without_a_visit_do_not_block_each_other(session, clinic):
    session.add(make_encounter(clinic))
    session.add(make_encounter(clinic))
    session.commit()

    assert len(stored(session, clinic)) == 2


@pytest.mark.parametrize(
    "missing", ["tenant_id", "patient_id", "appointment_id", "clinician_id", "closed_by_id"]
)
def test_every_link_must_point_at_something_real(session, clinic, missing):
    session.add(make_encounter(clinic, **{missing: uuid.uuid4()}))

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
