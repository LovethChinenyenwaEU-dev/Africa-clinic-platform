from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import ACTIVE_STATUSES, AppointmentStatus

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "branch_id",
    "patient_id",
    "clinician_id",
    "kind",
    "visit_type",
    "status",
    "starts_at",
    "ends_at",
    "checked_in_at",
    "consult_started_at",
    "completed_at",
    "created_by_id",
    "booked_via",  # staff or patient_portal (Week 9)
    "created_at",
}


def test_appointment_table_holds_only_ids_codes_and_times():
    """No notes or reason columns. If someone adds one, they must stop and think."""
    assert set(Appointment.__table__.columns.keys()) == ALLOWED_COLUMNS


def test_only_unfinished_appointments_occupy_a_clinicians_time():
    assert ACTIVE_STATUSES == {
        AppointmentStatus.BOOKED,
        AppointmentStatus.WAITING,
        AppointmentStatus.IN_CONSULT,
    }