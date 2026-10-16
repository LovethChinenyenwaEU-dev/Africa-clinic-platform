"""Week 8 Step 8: offline chaos. Writes queued on three devices arrive shuffled,
repeated, and after sign-off. Whatever the order, nothing is lost, nothing is
doubled, and every disagreement ends as exactly one version in use.

The order is random but seeded, so a failure can be replayed exactly.
"""
import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.audit.service import list_audit_events
from app.modules.records.models import ClinicalNote, VitalSigns
from app.modules.records.notes import amend_note, resolve_note_conflict, write_note
from app.modules.records.service import close_encounter, open_encounter
from app.modules.records.vitals import (
    VitalReadings,
    correct_vitals,
    record_vitals,
    resolve_vitals_conflict,
)
from tests.scheduling_helpers import build_clinic

SEEDS = range(12)


@pytest.fixture
def clinic(session, run_id):
    return build_clinic(session, run_id, "a")


def who(clinic, person):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def interleave(rng, queues):
    """Mix the devices' queues; each device still sends its own writes in order."""
    queues = [list(queue) for queue in queues]
    mixed = []
    while any(queues):
        queue = rng.choice([queue for queue in queues if queue])
        mixed.append(queue.pop(0))
    return mixed


def with_replays(rng, deliveries):
    """Each write may be sent again later (the answer was lost, so the device retried)."""
    result = list(deliveries)
    for op in deliveries:
        for _ in range(rng.randint(0, 2)):
            first = result.index(op)
            result.insert(rng.randint(first + 1, len(result)), op)
    return result


@pytest.mark.parametrize("seed", SEEDS)
def test_offline_writes_survive_any_order_replays_and_sign_off(session, clinic, seed):
    rng = random.Random(seed)
    now = datetime.now(UTC)
    opened = now - timedelta(hours=2)
    during = now - timedelta(minutes=90)  # every offline write was made while still open
    closed = now - timedelta(hours=1)
    ids = {name: uuid.uuid4() for name in ("v1", "va", "vb", "v2", "n1", "nb", "nc", "n2")}

    # Online, before anyone lost the network: one set of vitals and one note.
    encounter = open_encounter(
        session, **who(clinic, "doctor"), patient_id=clinic["patient"].id, now=opened
    )
    record_vitals(
        session,
        **who(clinic, "nurse"),
        encounter_id=encounter.id,
        readings=VitalReadings(pulse_bpm=100),
        measured_at=during,
        vitals_id=ids["v1"],
    )
    write_note(
        session,
        **who(clinic, "doctor"),
        encounter_id=encounter.id,
        kind="history",
        body="Fever.",
        note_id=ids["n1"],
        written_at=during,
    )

    # Offline, on three devices. Each queues its writes in order.
    def nurse_tablet():
        return [
            lambda: record_vitals(
                session,
                **who(clinic, "nurse"),
                encounter_id=encounter.id,
                readings=VitalReadings(temperature_c=Decimal("38.2")),
                measured_at=during,
                vitals_id=ids["v2"],
            ),
            lambda: correct_vitals(
                session,
                **who(clinic, "nurse"),
                vitals_id=ids["v1"],
                readings=VitalReadings(pulse_bpm=96),
                correction_id=ids["va"],
            ),
        ]

    def doctor_laptop():
        return [
            lambda: correct_vitals(
                session,
                **who(clinic, "doctor"),
                vitals_id=ids["v1"],
                readings=VitalReadings(pulse_bpm=104),
                correction_id=ids["vb"],
            ),
            lambda: amend_note(
                session, **who(clinic, "doctor"), note_id=ids["n1"], body="Fever, 3 days.",
                amendment_id=ids["nb"],
            ),
            lambda: write_note(
                session,
                **who(clinic, "doctor"),
                encounter_id=encounter.id,
                kind="assessment",
                body="Likely malaria.",
                note_id=ids["n2"],
                written_at=during,
            ),
        ]

    def doctor_phone():
        return [
            lambda: amend_note(
                session, **who(clinic, "doctor"), note_id=ids["n1"], body="Fever, 4 days.",
                amendment_id=ids["nc"],
            ),
        ]

    # The doctor signs off (on a device that was online) before any of it arrives.
    close_encounter(session, **who(clinic, "doctor"), encounter_id=encounter.id, now=closed)

    queued = interleave(rng, [nurse_tablet(), doctor_laptop(), doctor_phone()])
    deliveries = with_replays(rng, queued)
    for send in deliveries:
        send()

    vitals = {row.id: row for row in session.exec(tenant_select(VitalSigns, clinic["tenant"].id))}
    notes = {row.id: row for row in session.exec(tenant_select(ClinicalNote, clinic["tenant"].id))}

    # Nothing lost, nothing doubled.
    assert set(vitals) == {ids[name] for name in ("v1", "va", "vb", "v2")}
    assert set(notes) == {ids[name] for name in ("n1", "nb", "nc", "n2")}

    # The two corrections of the same set: one in use, one waiting as a conflict.
    assert vitals[ids["v1"]].status == "superseded"
    assert sorted([vitals[ids["va"]].status, vitals[ids["vb"]].status]) == ["conflict", "current"]
    assert sorted([notes[ids["nb"]].version_status, notes[ids["nc"]].version_status]) == [
        "conflict",
        "current",
    ]
    assert notes[ids["n1"]].version_status == "superseded"

    # Taken before sign-off, arrived after it: accepted, and marked.
    assert vitals[ids["v2"]].status == "current" and vitals[ids["v2"]].synced_late
    assert notes[ids["n2"]].version_status == "current" and notes[ids["n2"]].synced_late
    assert not vitals[ids["v1"]].synced_late and not notes[ids["n1"]].synced_late

    # One diary line per real write, however many times it was sent.
    actions = [event.action for event in list_audit_events(session, tenant_id=clinic["tenant"].id)]
    for action, count in {
        "vitals.record": 2,
        "vitals.correct": 2,
        "note.write": 2,
        "note.amend": 2,
    }.items():
        assert actions.count(action) == count, action

    # A clinician settles both conflicts: exactly one version in use per chain.
    vitals_conflict = next(i for i in ("va", "vb") if vitals[ids[i]].status == "conflict")
    note_conflict = next(i for i in ("nb", "nc") if notes[ids[i]].version_status == "conflict")
    resolve_vitals_conflict(
        session, **who(clinic, "doctor"), conflict_id=ids[vitals_conflict], keep_conflict=True
    )
    resolve_note_conflict(
        session, **who(clinic, "doctor"), conflict_id=ids[note_conflict], keep_conflict=False
    )

    session.expire_all()
    vitals = {
        row.id: row.status
        for row in session.exec(tenant_select(VitalSigns, clinic["tenant"].id))
    }
    notes = {
        row.id: row.version_status
        for row in session.exec(tenant_select(ClinicalNote, clinic["tenant"].id))
    }
    assert vitals[ids[vitals_conflict]] == "current"
    assert [vitals[ids[name]] for name in ("va", "vb")].count("current") == 1
    assert [notes[ids[name]] for name in ("nb", "nc")].count("current") == 1
    assert "conflict" not in vitals.values() and "conflict" not in notes.values()
