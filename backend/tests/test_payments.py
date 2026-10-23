"""Week 10 Step 3: cash and transfer payments, receipts and what is still owed (FR-B2)."""
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing.invoices import (
    add_line,
    issue_invoice,
    start_invoice,
    view_invoice,
    void_invoice,
)
from app.modules.billing.money import naira
from app.modules.billing.payments import (
    DuplicateTransferError,
    InvalidPaymentError,
    PaymentNotAllowedError,
    PaymentNotFoundError,
    record_payment,
    view_receipt,
)
from app.modules.billing.prices import add_price
from app.modules.identity.service import create_staff, login
from tests.scheduling_helpers import PASSWORD, book, build_clinic

CONSULT = 500_000  # 5,000 naira
MALARIA_TEST = 150_000  # 1,500 naira
TOTAL = CONSULT + MALARIA_TEST


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def bill_visit(session, clinic, visit, issue=True):
    """An invoice for the visit with a consultation and a malaria test."""
    invoice = start_invoice(session, **who(clinic), appointment_id=visit.id)
    for service in ("consult", "malaria"):
        add_line(session, **who(clinic), invoice_id=invoice.id, price_item_id=clinic[service].id)
    if issue:
        issue_invoice(session, **who(clinic), invoice_id=invoice.id)
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
        clinic["consult"] = add_price(session, **admin, name="GP consultation", price_kobo=CONSULT)
        clinic["malaria"] = add_price(
            session, **admin, name="Malaria test", price_kobo=MALARIA_TEST
        )
        clinic["visit"] = book(session, clinic)
        clinic["invoice"] = bill_visit(session, clinic, clinic["visit"])
        data[label] = clinic
    return data


def pay(session, clinic, amount, method="cash", reference=None, person="desk", **extra):
    return record_payment(
        session,
        **who(clinic, person),
        invoice_id=clinic["invoice"].id,
        method=method,
        amount_kobo=amount,
        reference=reference,
        **extra,
    )


def state(session, clinic):
    result = view_invoice(session, **who(clinic), invoice_id=clinic["invoice"].id)
    return result.payment_status.value, result.paid_kobo, result.balance_kobo


def payment_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [e for e in events if e.action == "payment.record"]


# --- taking money ------------------------------------------------------------------


def test_part_payments_add_up_to_paid(session, clinics):
    a = clinics["a"]
    assert state(session, a) == ("unpaid", 0, TOTAL)

    cash = pay(session, a, 200_000)
    assert state(session, a) == ("part_paid", 200_000, TOTAL - 200_000)
    transfer = pay(session, a, TOTAL - 200_000, method="transfer", reference="FBN 2210 7781")

    assert state(session, a) == ("paid", TOTAL, 0)
    assert (cash.receipt_number, transfer.receipt_number) == ("RCT-000001", "RCT-000002")
    assert transfer.reference == "FBN 2210 7781"
    assert cash.received_by_id == a["desk"].id
    lines = payment_lines(session, a)
    assert {(e.entity_id, e.patient_id) for e in lines} == {
        (cash.id, a["patient"].id),
        (transfer.id, a["patient"].id),
    }


def test_nobody_takes_more_than_is_owed(session, clinics):
    a = clinics["a"]
    pay(session, a, CONSULT)

    with pytest.raises(InvalidPaymentError, match=re.escape(naira(MALARIA_TEST))):
        pay(session, a, MALARIA_TEST + 1)
    pay(session, a, MALARIA_TEST)
    with pytest.raises(PaymentNotAllowedError):
        pay(session, a, 1)

    assert state(session, a) == ("paid", TOTAL, 0)


def test_a_draft_or_void_invoice_takes_no_money(session, clinics):
    a = clinics["a"]
    second_visit = book(session, a, starts_at=a["visit"].starts_at.replace(hour=11))
    draft = bill_visit(session, a, second_visit, issue=False)

    with pytest.raises(PaymentNotAllowedError):
        record_payment(
            session, **who(a), invoice_id=draft.id, method="cash", amount_kobo=CONSULT
        )
    void_invoice(session, **who(a), invoice_id=draft.id, reason="Billed the wrong visit")
    with pytest.raises(PaymentNotAllowedError):
        record_payment(
            session, **who(a), invoice_id=draft.id, method="cash", amount_kobo=CONSULT
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"amount": -100},
        {"amount": True},
        {"amount": 1.5},
        {"method": "card"},
        {"method": "transfer", "reference": None},
        {"method": "transfer", "reference": "  "},
        {"method": "transfer", "reference": "ab"},
        {"reference": "x" * 61},
    ],
)
def test_bad_payments_are_refused_and_nothing_is_saved(session, clinics, changes):
    a = clinics["a"]
    values = {"amount": 1000, "method": "cash", "reference": None} | changes

    with pytest.raises(InvalidPaymentError):
        pay(session, a, values["amount"], method=values["method"], reference=values["reference"])

    assert state(session, a) == ("unpaid", 0, TOTAL)
    assert payment_lines(session, a) == []


def test_one_bank_transfer_is_recorded_once(session, clinics):
    a, b = clinics["a"], clinics["b"]
    pay(session, a, 100_000, method="transfer", reference="GTB-5521")
    second_visit = book(session, a, starts_at=a["visit"].starts_at.replace(hour=11))
    other_invoice = bill_visit(session, a, second_visit)

    with pytest.raises(DuplicateTransferError):
        pay(session, a, 100_000, method="transfer", reference="gtb-5521")
    with pytest.raises(DuplicateTransferError):  # even on another invoice
        record_payment(
            session,
            **who(a),
            invoice_id=other_invoice.id,
            method="transfer",
            amount_kobo=100_000,
            reference=" GTB-5521 ",
        )
    # Another clinic's bank may use the same reference.
    assert pay(session, b, 100_000, method="transfer", reference="GTB-5521").amount_kobo == 100_000


def test_the_same_payment_sent_twice_is_recorded_once(session, clinics):
    a = clinics["a"]
    payment_id = uuid.uuid4()

    first = pay(session, a, 100_000, payment_id=payment_id)
    again = pay(session, a, 100_000, payment_id=payment_id)

    assert first.id == again.id == payment_id
    assert state(session, a) == ("part_paid", 100_000, TOTAL - 100_000)
    assert len(payment_lines(session, a)) == 1


def test_each_clinic_counts_its_own_receipts(session, clinics):
    first_a = pay(session, clinics["a"], 100)
    first_b = pay(session, clinics["b"], 100)
    second_a = pay(session, clinics["a"], 100)

    assert (first_a.receipt_number, second_a.receipt_number) == ("RCT-000001", "RCT-000002")
    assert first_b.receipt_number == "RCT-000001"


# --- receipts --------------------------------------------------------------------------


def test_a_receipt_shows_what_was_paid_and_what_is_left(session, clinics):
    a = clinics["a"]
    first = pay(session, a, 200_000)
    second = pay(session, a, 100_000, method="transfer", reference="UBA-0091")

    receipt = view_receipt(session, **who(a, "billing"), payment_id=first.id)
    later = view_receipt(session, **who(a, "billing"), payment_id=second.id)

    assert receipt.clinic_name == a["tenant"].name
    assert receipt.patient_name == "Test Patient A"
    assert receipt.invoice_number == "INV-000001"
    assert receipt.invoice_total_kobo == TOTAL
    assert (receipt.paid_to_date_kobo, receipt.balance_after_kobo) == (200_000, TOTAL - 200_000)
    assert (later.paid_to_date_kobo, later.balance_after_kobo) == (300_000, TOTAL - 300_000)
    assert receipt.received_by_name == "Test front_desk"
    assert re.fullmatch(r"[0-9A-F]{10}", receipt.check_code)
    assert receipt.check_code != later.check_code
    again = view_receipt(session, **who(a, "billing"), payment_id=first.id)
    assert again.check_code == receipt.check_code  # the same receipt, the same code
    views = [
        e for e in list_audit_events(session, tenant_id=a["tenant"].id)
        if e.action == "receipt.view"
    ]
    assert len(views) == 3
    assert {e.patient_id for e in views} == {a["patient"].id}


def test_another_clinics_receipt_is_not_found(session, clinics):
    theirs = pay(session, clinics["b"], 100)

    with pytest.raises(PaymentNotFoundError):
        view_receipt(session, **who(clinics["a"]), payment_id=theirs.id)


# --- the doors --------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, role, label="a"):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_billing_takes_payment_and_prints_a_receipt(client, session, run_id, clinics):
    a = clinics["a"]
    billing = bearer(session, run_id, "billing")
    invoice_url = f"/api/v1/billing/invoices/{a['invoice'].id}"

    taken = client.post(
        f"{invoice_url}/payments", json={"method": "cash", "amount_kobo": CONSULT}, headers=billing
    )
    as_text = client.post(
        f"{invoice_url}/payments", json={"method": "cash", "amount_kobo": "1500"}, headers=billing
    )
    too_much = client.post(
        f"{invoice_url}/payments", json={"method": "cash", "amount_kobo": TOTAL}, headers=billing
    )
    invoice = client.get(invoice_url, headers=billing).json()
    listed = client.get(f"/api/v1/billing/patients/{a['patient'].id}/invoices", headers=billing)
    receipt = client.get(f"/api/v1/billing/payments/{taken.json()['id']}/receipt", headers=billing)

    assert taken.status_code == 201
    assert taken.json()["receipt_number"] == "RCT-000001"
    assert as_text.status_code == 422
    assert too_much.status_code == 422
    assert (invoice["payment_status"], invoice["paid_kobo"], invoice["balance_kobo"]) == (
        "part_paid",
        CONSULT,
        MALARIA_TEST,
    )
    assert [p["receipt_number"] for p in invoice["payments"]] == ["RCT-000001"]
    assert listed.json()[0]["payment_status"] == "part_paid"
    assert receipt.status_code == 200
    assert receipt.json()["balance_after_kobo"] == MALARIA_TEST


def test_only_front_desk_and_billing_take_money(client, session, run_id, clinics):
    a = clinics["a"]
    url = f"/api/v1/billing/invoices/{a['invoice'].id}/payments"
    body = {"method": "cash", "amount_kobo": 100}

    for role in ("nurse", "doctor", "admin"):
        refused = client.post(url, json=body, headers=bearer(session, run_id, role))
        assert refused.status_code == 403
    taken = client.post(url, json=body, headers=bearer(session, run_id, "front_desk"))
    admin_reads = client.get(
        f"/api/v1/billing/payments/{taken.json()['id']}/receipt",
        headers=bearer(session, run_id, "admin"),
    )

    assert taken.status_code == 201
    assert admin_reads.status_code == 200


def test_a_repeated_transfer_gets_409_through_the_api(client, session, run_id, clinics):
    a = clinics["a"]
    url = f"/api/v1/billing/invoices/{a['invoice'].id}/payments"
    body = {"method": "transfer", "amount_kobo": 100, "reference": "ACC-778899"}
    billing = bearer(session, run_id, "billing")

    first = client.post(url, json=body, headers=billing)
    second = client.post(url, json=body, headers=billing)
    elsewhere = client.post(
        f"/api/v1/billing/invoices/{clinics['b']['invoice'].id}/payments",
        json={"method": "cash", "amount_kobo": 100},
        headers=billing,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert elsewhere.status_code == 404
