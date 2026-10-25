"""Week 10 Step 6: the daily takings and what needs a second look."""
import csv
import io
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing import online
from app.modules.billing.gateway import FakeGateway, GatewayResult
from app.modules.billing.invoices import add_line, issue_invoice, start_invoice
from app.modules.billing.online import handle_webhook, start_online_payment
from app.modules.billing.payments import record_payment
from app.modules.billing.prices import add_price
from app.modules.billing.refunds import approve_refund, request_refund
from app.modules.billing.takings import daily_takings, takings_csv
from app.modules.identity.service import create_staff, login
from app.modules.scheduling.board import lagos_day
from tests.dates import MONDAY, utc
from tests.scheduling_helpers import NOW, PASSWORD, book, build_clinic

CONSULT = 500_000  # 5,000 naira
MALARIA_TEST = 150_000  # 1,500 naira


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def bill(session, clinic, visit, services, issued_at=None):
    invoice = start_invoice(session, **who(clinic), appointment_id=visit.id)
    for service in services:
        add_line(session, **who(clinic), invoice_id=invoice.id, price_item_id=clinic[service].id)
    issue_invoice(session, **who(clinic), invoice_id=invoice.id, now=issued_at)
    return invoice


@pytest.fixture
def clinics(session, run_id):
    data = {}
    for label in ("a", "b"):
        clinic = build_clinic(session, run_id, label)
        for role in ("admin", "billing"):
            clinic[role] = create_staff(
                session,
                tenant_id=clinic["tenant"].id,
                email=f"{label}-{role}@{run_id}.example.com",
                full_name=f"Test {role}",
                role=role,
                password=PASSWORD,
            )
        admin = who(clinic, "admin")
        clinic["consult"] = add_price(session, **admin, name="Consult", price_kobo=CONSULT)
        clinic["malaria"] = add_price(session, **admin, name="Malaria", price_kobo=MALARIA_TEST)
        later = book(session, clinic, starts_at=NOW.replace(hour=11))
        clinic["visits"] = [book(session, clinic), later]
        data[label] = clinic
    return data


def pay(session, clinic, invoice, amount, at=None, method="cash", person="desk", reference=None):
    return record_payment(
        session,
        **who(clinic, person),
        invoice_id=invoice.id,
        method=method,
        amount_kobo=amount,
        reference=reference,
        now=at,
    )


def ask(session, clinic, payment, amount, person="desk", at=None):
    return request_refund(
        session,
        **who(clinic, person),
        payment_id=payment.id,
        amount_kobo=amount,
        method="cash",
        reason="Test not done",
        now=at,
    )


@pytest.fixture
def busy_monday(session, clinics):
    """Clinic A's Monday: two invoices, four payments (one after midnight), one refund.
    Clinic B takes money the same day, which A must never see."""
    a, b = clinics["a"], clinics["b"]
    first = bill(session, a, a["visits"][0], ["consult", "malaria"], utc(MONDAY, 8))
    second = bill(session, a, a["visits"][1], ["consult"], utc(MONDAY, 8, 30))
    cash = pay(session, a, first, CONSULT, utc(MONDAY, 9))
    pay(session, a, first, MALARIA_TEST, utc(MONDAY, 10), "transfer", "billing", "GTB-001")
    pay(session, a, second, 200_000, utc(MONDAY, 11))
    pay(session, a, second, 300_000, utc(MONDAY, 23, 30))  # 00:30 Tuesday in Lagos
    refund = ask(session, a, cash, 100_000, person="billing", at=utc(MONDAY, 12))
    approve_refund(
        session, **who(a, "admin"), refund_id=refund.id, now=utc(MONDAY, 13)
    )
    theirs = bill(session, b, b["visits"][0], ["consult"], utc(MONDAY, 8))
    pay(session, b, theirs, CONSULT, utc(MONDAY, 9))
    return a


def totals(rows):
    return [(row.method, row.count, row.amount_kobo) for row in rows]


def test_the_days_money_in_and_out_by_method_and_person(session, busy_monday):
    a = busy_monday

    day = daily_takings(session, **who(a, "billing"), day=MONDAY)

    assert totals(day.money_in) == [("cash", 2, 700_000), ("transfer", 1, MALARIA_TEST)]
    assert totals(day.money_out) == [("cash", 1, 100_000)]
    assert totals(day.net_by_method) == [("cash", 3, 600_000), ("transfer", 1, MALARIA_TEST)]
    assert (day.total_in_kobo, day.total_out_kobo, day.net_kobo) == (850_000, 100_000, 750_000)
    assert [(s.name, s.payments, s.taken_kobo) for s in day.by_staff] == [
        ("Test front_desk", 2, 700_000),
        ("Test billing", 1, MALARIA_TEST),
    ]
    assert (day.invoices_issued, day.billed_kobo) == (2, CONSULT + MALARIA_TEST + CONSULT)
    assert day.flags == []
    actions = [e.action for e in list_audit_events(session, tenant_id=a["tenant"].id)]
    assert "takings.view" in actions


def test_the_next_lagos_day_starts_at_midnight_lagos_time(session, busy_monday):
    a = busy_monday

    day = daily_takings(
        session, **who(a, "billing"), day=lagos_day(utc(MONDAY, 23, 30))
    )

    assert totals(day.money_in) == [("cash", 1, 300_000)]  # only the 00:30 payment


def test_the_export_has_numbers_and_amounts_but_no_patient_names(session, busy_monday):
    a = busy_monday

    filename, text = takings_csv(session, **who(a, "admin"), day=MONDAY)

    rows = list(csv.reader(io.StringIO(text)))
    assert filename == f"takings-{MONDAY.isoformat()}.csv"
    assert rows[0] == [
        "time", "kind", "number", "invoice", "method", "amount_naira", "staff", "reference"
    ]
    assert rows[1:] == [
        ["10:00", "payment", "RCT-000001", "INV-000001", "cash", "5000.00", "Test front_desk", ""],
        [
            "11:00", "payment", "RCT-000002", "INV-000001", "transfer", "1500.00",
            "Test billing", "GTB-001",
        ],
        ["12:00", "payment", "RCT-000003", "INV-000002", "cash", "2000.00", "Test front_desk", ""],
        ["14:00", "refund", "RFD-000001", "INV-000001", "cash", "-1000.00", "Test admin", ""],
    ]
    assert "Test Patient" not in text
    assert "takings.export" in [
        e.action for e in list_audit_events(session, tenant_id=a["tenant"].id)
    ]


# --- things to look at ---------------------------------------------------------------------


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(online, "payment_gateway", lambda: fake)
    return fake


def webhook(session, gateway, reference, status):
    gateway.outcomes[reference] = GatewayResult(status, gateway_amount(gateway, reference), "NGN")
    body = json.dumps({"event": "charge.success", "data": {"reference": reference}}).encode()
    handle_webhook(session, body=body, signature=gateway.sign(body))


def gateway_amount(gateway, reference):
    return next(i["amount_kobo"] for i in gateway.initialized if i["reference"] == reference)


def test_unusual_refunds_overpaid_bills_and_failed_payments_are_flagged(
    session, clinics, gateway
):
    a = clinics["a"]
    today = lagos_day(datetime.now(UTC))  # online payments are stamped with the real clock
    first = bill(session, a, a["visits"][0], ["consult", "malaria"])
    second = bill(session, a, a["visits"][1], ["consult"])
    own_cash = pay(session, a, first, CONSULT)
    their_transfer = pay(session, a, first, MALARIA_TEST, None, "transfer", "billing", "UBA-9")
    # The front desk asks for all of its own cash back, then three more small refunds.
    ask(session, a, own_cash, CONSULT)
    for _ in range(3):
        ask(session, a, their_transfer, 10_000)
    # Two links for the second bill; cash settles it, then one link is paid anyway.
    full = start_online_payment(session, **who(a), invoice_id=second.id)
    part = start_online_payment(session, **who(a), invoice_id=second.id, amount_kobo=200_000)
    pay(session, a, second, CONSULT)
    webhook(session, gateway, full.reference, "success")
    webhook(session, gateway, part.reference, "failed")

    flags = daily_takings(session, **who(a, "admin"), day=today).flags

    kinds = {flag.kind for flag in flags}
    assert kinds == {
        "overpaid",
        "refund_waiting",
        "online_failed",
        "whole_refund",
        "own_refund",
        "many_refunds",
    }
    overpaid = next(f for f in flags if f.kind == "overpaid")
    assert (overpaid.invoice_number, overpaid.amount_kobo) == ("INV-000002", CONSULT)
    waiting = next(f for f in flags if f.kind == "refund_waiting")
    assert waiting.amount_kobo == CONSULT + 3 * 10_000
    own = [f for f in flags if f.kind == "own_refund"]
    assert len(own) == 1 and "Test front_desk" in own[0].message
    assert [f.invoice_number for f in flags if f.kind == "whole_refund"] == ["INV-000001"]
    assert "4 refunds" in next(f for f in flags if f.kind == "many_refunds").message


# --- the doors ------------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, role):
    token = login(session, email=f"a-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_billing_and_admins_read_the_takings_others_do_not(client, session, run_id, busy_monday):
    url = f"/api/v1/billing/takings?day={MONDAY.isoformat()}"

    for role in ("front_desk", "nurse", "doctor"):
        assert client.get(url, headers=bearer(session, run_id, role)).status_code == 403
    by_billing = client.get(url, headers=bearer(session, run_id, "billing"))
    by_admin = client.get(url, headers=bearer(session, run_id, "admin"))
    export = client.get(
        f"/api/v1/billing/takings/export?day={MONDAY.isoformat()}",
        headers=bearer(session, run_id, "admin"),
    )
    today = client.get("/api/v1/billing/takings", headers=bearer(session, run_id, "admin"))
    bad_day = client.get(
        "/api/v1/billing/takings?day=25/10/2026", headers=bearer(session, run_id, "admin")
    )

    assert by_billing.status_code == 200
    assert by_billing.json()["net_kobo"] == 750_000
    assert by_admin.json()["money_in"][0] == {"method": "cash", "count": 2, "amount_kobo": 700_000}
    assert export.json()["filename"].endswith(".csv")
    assert export.json()["csv"].startswith("time,kind,number")
    assert today.status_code == 200
    assert bad_day.status_code == 422
