"""Week 11 Step 5: the clinic dashboard (P-11): waits, no-shows, completion, sync,
revenue and record access, as counts and sums only."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing.invoices import add_line, issue_invoice, start_invoice
from app.modules.billing.payments import record_payment
from app.modules.billing.prices import add_price
from app.modules.identity.service import create_staff, login
from app.modules.patients.models import ReviewStatus
from app.modules.reports.dashboard import (
    BadRangeError,
    check_range,
    count_visits,
    median,
    percentile,
    wait_minutes,
)
from app.modules.scheduling.models import Appointment
from tests.dates import MONDAY, utc
from tests.scheduling_helpers import PASSWORD, book, build_clinic

URL = "/api/v1/reports/dashboard"
CONSULT = 500_000  # 5,000 naira


def appointment(clinic, *, hour, kind="scheduled", status="booked", waited=None, day=MONDAY):
    """A visit as it ended up, put straight in the table: the dashboard only counts."""
    starts = utc(day, hour)
    came = waited is not None or status in ("waiting", "in_consult", "done")
    checked_in = starts if came else None
    return Appointment(
        tenant_id=clinic["tenant"].id,
        branch_id=clinic["branch"].id,
        patient_id=clinic["patient"].id,
        kind=kind,
        visit_type="in_person",
        status=status,
        starts_at=starts,
        ends_at=starts + timedelta(minutes=15),
        checked_in_at=checked_in,
        consult_started_at=starts + timedelta(minutes=waited) if waited is not None else None,
    )


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        clinic = build_clinic(session, run_id, label)
        for role in ("admin", "billing"):
            clinic[role] = create_staff(
                session,
                tenant_id=clinic["tenant"].id,
                email=f"dash-{label}-{role}@{run_id}.example.com",
                full_name=f"Test {role}",
                role=role,
                password=PASSWORD,
            )
        data[label] = clinic
    return data


@pytest.fixture
def monday(session, clinics):
    """Clinic A's Monday: 6 visits and one cash payment. Clinic B has a busy day too."""
    a = clinics["a"]
    rows = [
        appointment(a, hour=8, status="done", waited=10),
        appointment(a, hour=9, status="done", waited=30),
        appointment(a, hour=10, status="in_consult", waited=50),  # came, not finished yet
        appointment(a, hour=11, kind="walk_in", status="done", waited=90),
        appointment(a, hour=12, status="no_show"),
        appointment(a, hour=13, status="cancelled"),
    ]
    rows += [appointment(clinics["b"], hour=h, status="no_show") for h in range(8, 12)]
    session.add_all(rows)
    session.commit()

    who = {"tenant_id": a["tenant"].id, "actor_id": a["admin"].id}
    price = add_price(session, **who, name="Consult", price_kobo=CONSULT)
    desk = {"tenant_id": a["tenant"].id, "actor_id": a["desk"].id}
    visit = book(session, a)
    invoice = start_invoice(session, **desk, appointment_id=visit.id)
    add_line(session, **desk, invoice_id=invoice.id, price_item_id=price.id)
    issue_invoice(session, **desk, invoice_id=invoice.id, now=utc(MONDAY, 10))
    record_payment(
        session,
        **desk,
        invoice_id=invoice.id,
        method="cash",
        amount_kobo=CONSULT,
        now=utc(MONDAY, 10, 30),
    )
    return clinics


BUILD_CLINIC_ROLES = {"desk": "front_desk", "doctor": "doctor", "nurse": "nurse"}


def headers(session, run_id, label, role):
    if role in BUILD_CLINIC_ROLES:  # made by build_clinic
        email = f"{label}-{BUILD_CLINIC_ROLES[role]}@{run_id}.example.com"
    else:
        email = f"dash-{label}-{role}@{run_id}.example.com"
    return {"Authorization": f"Bearer {login(session, email=email, password=PASSWORD)}"}


def monday_only():
    return {"from_day": MONDAY.isoformat(), "to_day": MONDAY.isoformat()}


# --- how each number is worked out (no database) ---------------------------------------


def test_rates_count_who_was_due_and_who_came():
    rows = [
        Appointment(kind="scheduled", status="done", checked_in_at=utc(MONDAY, 9)),
        Appointment(kind="scheduled", status="waiting", checked_in_at=utc(MONDAY, 9)),
        Appointment(kind="scheduled", status="no_show"),
        Appointment(kind="walk_in", status="done", checked_in_at=utc(MONDAY, 9)),
        Appointment(kind="scheduled", status="cancelled"),
        Appointment(kind="scheduled", status="booked"),
    ]

    visits = count_visits(rows)

    assert (visits.total, visits.walk_ins, visits.done, visits.no_shows) == (6, 1, 2, 1)
    assert (visits.cancelled, visits.still_open, visits.checked_in) == (1, 2, 3)
    assert visits.no_show_rate == round(1 / 3, 3)  # 1 no-show; 2 booked patients came
    assert visits.completion_rate == round(2 / 3, 3)  # 3 came in; 2 finished


def test_no_rates_when_nobody_was_due():
    visits = count_visits([Appointment(kind="scheduled", status="cancelled")])

    assert visits.no_show_rate is None
    assert visits.completion_rate is None


def test_waits_are_check_in_to_consultation_start():
    rows = [
        Appointment(checked_in_at=utc(MONDAY, 9), consult_started_at=utc(MONDAY, 9, 25)),
        Appointment(checked_in_at=utc(MONDAY, 9)),  # still waiting: not measured
        Appointment(),
    ]

    assert wait_minutes(rows) == [25.0]


def test_median_and_90th_percentile():
    waits = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    assert median(waits) == 55.0
    assert percentile(waits, 0.9) == 90.0
    assert median([]) is None
    assert percentile([], 0.9) is None


def test_days_must_be_in_order_and_not_too_many():
    check_range(date(2026, 1, 1), date(2026, 1, 1))
    check_range(date(2026, 1, 1), date(2026, 4, 2))  # 92 days
    with pytest.raises(BadRangeError):
        check_range(date(2026, 1, 2), date(2026, 1, 1))
    with pytest.raises(BadRangeError):
        check_range(date(2026, 1, 1), date(2026, 4, 3))


# --- through the API -------------------------------------------------------------------


def test_admin_sees_the_days_numbers(session, run_id, monday):
    response = TestClient(app).get(
        URL, params=monday_only(), headers=headers(session, run_id, "a", "admin")
    )

    assert response.status_code == 200
    body = response.json()
    visits = body["visits"]
    # 6 visits put in, plus the one booked to bill (still booked).
    assert (visits["total"], visits["done"], visits["no_shows"], visits["cancelled"]) == (
        7,
        3,
        1,
        1,
    )
    assert visits["checked_in"] == 4
    assert visits["no_show_rate"] == 0.25  # 1 no-show; 3 booked patients came
    assert visits["completion_rate"] == 0.75
    assert body["waits"] == {
        "measured": 4,
        "median_minutes": 40.0,
        "p90_minutes": 90.0,
        "over_an_hour": 1,
    }
    revenue = body["revenue"]
    assert (revenue["invoices_issued"], revenue["billed_kobo"]) == (1, CONSULT)
    assert (revenue["payments"], revenue["received_kobo"], revenue["net_kobo"]) == (
        1,
        CONSULT,
        CONSULT,
    )
    assert revenue["by_method"] == [{"method": "cash", "count": 1, "amount_kobo": CONSULT}]
    assert [day["day"] for day in body["days"]] == [MONDAY.isoformat()]
    assert body["days"][0]["received_kobo"] == CONSULT


def test_no_patient_details_are_shown(session, run_id, monday):
    response = TestClient(app).get(
        URL, params=monday_only(), headers=headers(session, run_id, "a", "admin")
    )

    text = response.text
    assert "Test Patient" not in text
    assert str(monday["a"]["patient"].id) not in text


def test_another_clinics_visits_are_not_counted(session, run_id, monday):
    body = (
        TestClient(app)
        .get(URL, params=monday_only(), headers=headers(session, run_id, "b", "admin"))
        .json()
    )

    assert body["visits"]["total"] == 4
    assert body["visits"]["no_shows"] == 4
    assert body["revenue"]["received_kobo"] == 0


def test_record_access_counts_staff_lines_about_patients(session, run_id, monday):
    body = (
        TestClient(app)
        .get(URL, headers=headers(session, run_id, "a", "admin"))  # the last 7 days: now
        .json()
    )

    access = body["record_access"]
    assert access["events"] >= 1  # registering the patient, at least
    assert access["patients"] == 1
    names = {row["name"] for row in access["by_staff"]}
    assert "Test front_desk" in names


def test_registrations_to_review_are_counted(session, run_id, monday):
    patient = monday["a"]["patient"]
    patient.review_status = ReviewStatus.NEEDS_REVIEW.value
    session.add(patient)
    session.commit()

    body = (
        TestClient(app)
        .get(URL, params=monday_only(), headers=headers(session, run_id, "a", "admin"))
        .json()
    )

    assert body["sync"]["registrations_to_review"] == 1
    assert set(body["sync"]) == {
        "late_entries",
        "open_conflicts",
        "registrations_to_review",
        "reminders_sent",
        "reminders_failed",
        "online_payments_failed",
    }


def test_opening_it_is_written_in_the_diary(session, run_id, monday):
    admin = headers(session, run_id, "a", "admin")
    TestClient(app).get(URL, params=monday_only(), headers=admin)

    actions = [
        event.action for event in list_audit_events(session, tenant_id=monday["a"]["tenant"].id)
    ]
    assert "report.view" in actions


def test_the_last_seven_days_when_no_days_are_given(session, run_id, clinics):
    body = TestClient(app).get(URL, headers=headers(session, run_id, "a", "admin")).json()

    assert len(body["days"]) == 7
    assert body["to_day"] == body["days"][-1]["day"]


@pytest.mark.parametrize("role", ["billing", "desk", "doctor", "nurse"])
def test_only_admins_open_it(session, run_id, clinics, role):
    response = TestClient(app).get(URL, headers=headers(session, run_id, "a", role))

    assert response.status_code == 403


def test_signed_out_gets_401():
    assert TestClient(app).get(URL).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"from_day": "2026-03-02", "to_day": "2026-03-01"},
        {"from_day": "2026-01-01", "to_day": "2026-12-31"},
        {"from_day": "not-a-day"},
    ],
)
def test_bad_days_are_refused(session, run_id, clinics, params):
    admin = headers(session, run_id, "a", "admin")

    response = TestClient(app).get(URL, params=params, headers=admin)

    assert response.status_code == 422
