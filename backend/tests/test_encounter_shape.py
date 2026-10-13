from app.modules.records.models import Encounter
from app.modules.records.statuses import ALLOWED_MOVES, EncounterStatus

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "patient_id",
    "appointment_id",
    "clinician_id",
    "status",
    "opened_at",
    "closed_at",
    "closed_by_id",
}


def test_encounter_table_holds_only_ids_codes_and_times():
    """Clinical content has its own tables. A notes column here means stop and think."""
    assert set(Encounter.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_only_an_open_encounter_can_change_status():
    assert ALLOWED_MOVES == {
        EncounterStatus.OPEN: {EncounterStatus.CLOSED, EncounterStatus.ENTERED_IN_ERROR},
        EncounterStatus.CLOSED: set(),
        EncounterStatus.ENTERED_IN_ERROR: set(),
    }
