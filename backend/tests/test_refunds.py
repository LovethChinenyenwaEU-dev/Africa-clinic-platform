"""Week 10 Step 4: refunds need two people (FR-B3)."""
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing.invoices import add_line, issue_invoice, start_invoice, view_invoice
from app.modules.billing.payments import record_payment
from app.modules.billing.prices import add_price
from app.modules.billing.refunds import (
    InvalidRefundError,
    OwnRefundError,
    RefundAlreadyDecidedError,
    RefundNotFoundError,
    approve_refund,
    list_refunds,
    reject_refund,
    request_refund,
)
from app.modules.identity.service import create_staff, login
from tests.scheduling_helpers import PASSWORD, book, build_clinic

CONSULT = 500_000  # 5,000 naira


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


@pytest.fixture
def clinics(session, run_id):
    """Two clinics, each with a 5,000 naira invoice paid in full in cash."""
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
        service = add_price(session, **who(clinic, "admin"), name="Consult", price_kobo=CONSULT)
        visit = book(session, clinic)
        invoice = start_invoice(session, **who(clinic), appointment_id=visit.id)
        add_line(session, **who(clinic), invoice_id=invoice.id, price_item_id=service.id)
        issue_invoice(session, **who(clinic), invoice_id=invoice.id)
        clinic["invoice"] = invoice
        clinic["payment"] = record_payment(
            session, **who(clinic), invoice_id=invoice.id, method="cash", amount_kobo=CONSULT
        )
        data[label] = clinic
    return data


def ask(session, clinic, amount, person="desk", method="cash", reason="Lab test not done", **extra):
    return request_refund(
        session,
        **who(clinic, person),
        payment_id=clinic["payment"].id,
        amount_kobo=amount,
        method=method,
        reason=reason,
        **extra,
    )


def approve(session, clinic, refund, person="admin", note=None):
    return approve_refund(session, **who(clinic, person), refund_id=refund.id, note=note)


def reject(session, clinic, refund, note="No proof of the test missing", person="admin"):
    return reject_refund(session, **who(clinic, person), refund_id=refund.id, note=note)


def money(session, clinic):
    view = view_invoice(session, **who(clinic), invoice_id=clinic["invoice"].id)
    return view.payment_status.value, view.paid_kobo, view.refunded_kobo, view.balance_kobo


def refund_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted(e.action for e in events if e.action.startswith("refund."))


# --- asking and deciding ---------------------------------------------------------------


def test_desk_asks_and_an_admin_approves(session, clinics):
    a = clinics["a"]
    asked = ask(session, a, CONSULT, method="transfer")

    assert asked.status == "requested"
    assert asked.refund_number is None
    assert money(session, a) == ("paid", CONSULT, 0, 0)  # nothing goes back yet

    approved = approve(session, a, asked)

    assert approved.status == "approved"
    assert approved.refund_number == "RFD-000001"
    assert approved.decided_by_id == a["admin"].id
    assert approved.method == "transfer"
    assert money(session, a) == ("refunded", CONSULT, CONSULT, 0)
    assert refund_actions(session, a) == ["refund.approve", "refund.request"]
    lines = list_audit_events(session, tenant_id=a["tenant"].id)
    assert {e.patient_id for e in lines if e.action.startswith("refund.")} == {a["patient"].id}


def test_a_part_refund_leaves_the_invoice_paid_and_owing_nothing(session, clinics):
    a = clinics["a"]
    approve(session, a, ask(session, a, 150_000))

    # The patient was given back 1,500 naira for a service not given: they owe nothing.
    assert money(session, a) == ("paid", CONSULT, 150_000, 0)


def test_whoever_asked_never_decides(session, clinics):
    a = clinics["a"]
    # The service would let an admin ask (the doors do not); they still cannot decide it.
    asked_by_admin = ask(session, a, 100_000, person="admin")

    with pytest.raises(OwnRefundError):
        approve(session, a, asked_by_admin, person="admin")
    with pytest.raises(OwnRefundError):
        reject(session, a, asked_by_admin, person="admin")
    assert approve(session, a, asked_by_admin, person="billing").status == "approved"


def test_the_database_refuses_one_person_deciding_too(session, clinics):
    a = clinics["a"]
    asked = ask(session, a, 100_000)
    asked.status = "rejected"
    asked.decided_by_id = asked.requested_by_id
    asked.decided_at = datetime.now(UTC)
    session.add(asked)

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_decision_is_final(session, clinics):
    a = clinics["a"]
    approved = approve(session, a, ask(session, a, 100_000))
    rejected = reject(session, a, ask(session, a, 100_000))

    with pytest.raises(RefundAlreadyDecidedError):
        approve(session, a, approved)
    with pytest.raises(RefundAlreadyDecidedError):
        reject(session, a, approved)
    with pytest.raises(RefundAlreadyDecidedError):
        approve(session, a, rejected)
    assert rejected.decision_note == "No proof of the test missing"


def test_rejecting_needs_a_reason_and_approving_may_have_one(session, clinics):
    a = clinics["a"]
    asked = ask(session, a, 100_000)

    with pytest.raises(InvalidRefundError):
        reject(session, a, asked, note=" ")
    approved = approve(session, a, asked, note="Checked with the lab")
    assert approved.decision_note == "Checked with the lab"


# --- never more than was paid ----------------------------------------------------------


def test_waiting_and_approved_requests_count_against_the_payment(session, clinics):
    a = clinics["a"]
    waiting = ask(session, a, 300_000)
    approve(session, a, ask(session, a, 150_000))

    with pytest.raises(InvalidRefundError, match=r"₦500\.00"):
        ask(session, a, 50_001)  # only 500 naira (50,000 kobo) is left
    reject(session, a, waiting)
    assert ask(session, a, 350_000).amount_kobo == 350_000  # a rejection frees the amount


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"amount": -5},
        {"amount": True},
        {"amount": 10.5},
        {"method": "card"},
        {"reason": "no"},
        {"reason": "x" * 301},
    ],
)
def test_bad_requests_are_refused_and_nothing_is_saved(session, clinics, changes):
    a = clinics["a"]
    values = {"amount": 1000, "method": "cash", "reason": "Lab test not done"} | changes

    with pytest.raises(InvalidRefundError):
        ask(session, a, values["amount"], method=values["method"], reason=values["reason"])

    assert refund_actions(session, a) == []


def test_the_same_request_sent_twice_is_saved_once(session, clinics):
    a = clinics["a"]
    refund_id = uuid.uuid4()

    first = ask(session, a, 100_000, refund_id=refund_id)
    again = ask(session, a, 100_000, refund_id=refund_id)

    assert first.id == again.id == refund_id
    assert refund_actions(session, a) == ["refund.request"]


def test_another_clinics_payments_and_refunds_are_not_found(session, clinics):
    a, b = clinics["a"], clinics["b"]
    theirs = ask(session, b, 100_000)

    with pytest.raises(RefundNotFoundError):
        request_refund(
            session,
            **who(a),
            payment_id=b["payment"].id,
            amount_kobo=100,
            method="cash",
            reason="Not ours",
        )
    with pytest.raises(RefundNotFoundError):
        approve(session, a, theirs)


# --- the admin's list ------------------------------------------------------------------


def test_the_admin_sees_waiting_refunds_first(session, clinics):
    a = clinics["a"]
    waiting = ask(session, a, 100_000)
    approve(session, a, ask(session, a, 100_000))
    ask(session, clinics["b"], 100_000)  # another clinic's

    assert [r.id for r in list_refunds(session, **who(a, "admin"))] == [waiting.id]
    approved = list_refunds(session, **who(a, "admin"), status="approved")
    assert [r.status for r in approved] == ["approved"]
    assert len(list_refunds(session, **who(a, "admin"), status=None)) == 2
    with pytest.raises(InvalidRefundError):
        list_refunds(session, **who(a, "admin"), status="maybe")
    assert "refund.list" in refund_actions(session, a)


# --- the doors -------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, role, label="a"):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_refunds_through_the_api_need_two_people(client, session, run_id, clinics):
    a = clinics["a"]
    ask_url = f"/api/v1/billing/payments/{a['payment'].id}/refunds"
    body = {"amount_kobo": 200_000, "method": "cash", "reason": "Overcharged for the consult"}
    billing = bearer(session, run_id, "billing")
    admin = bearer(session, run_id, "admin")

    by_nurse = client.post(ask_url, json=body, headers=bearer(session, run_id, "nurse"))
    by_admin = client.post(ask_url, json=body, headers=admin)  # admins decide, never ask
    asked = client.post(ask_url, json=body, headers=billing)
    decide_url = f"/api/v1/billing/refunds/{asked.json()['id']}"
    billing_lists = client.get("/api/v1/billing/refunds", headers=billing)
    billing_approves = client.post(f"{decide_url}/approve", json={}, headers=billing)
    waiting = client.get("/api/v1/billing/refunds", headers=admin)
    approved = client.post(f"{decide_url}/approve", json={"note": "Agreed"}, headers=admin)
    again = client.post(f"{decide_url}/reject", json={"note": "Too late"}, headers=admin)
    invoice = client.get(f"/api/v1/billing/invoices/{a['invoice'].id}", headers=billing).json()

    assert by_nurse.status_code == 403
    assert by_admin.status_code == 403
    assert asked.status_code == 201
    assert billing_lists.status_code == 403
    assert billing_approves.status_code == 403
    assert [r["id"] for r in waiting.json()] == [asked.json()["id"]]
    assert approved.status_code == 200
    assert approved.json()["refund_number"] == "RFD-000001"
    assert again.status_code == 409
    assert invoice["refunded_kobo"] == 200_000
    assert [r["status"] for r in invoice["refunds"]] == ["approved"]


def test_too_much_or_a_missing_reason_gets_422(client, session, run_id, clinics):
    a = clinics["a"]
    ask_url = f"/api/v1/billing/payments/{a['payment'].id}/refunds"
    billing = bearer(session, run_id, "billing")

    too_much = client.post(
        ask_url,
        json={"amount_kobo": CONSULT + 1, "method": "cash", "reason": "Overcharged"},
        headers=billing,
    )
    asked = client.post(
        ask_url,
        json={"amount_kobo": 100, "method": "cash", "reason": "Overcharged"},
        headers=billing,
    )
    no_reason = client.post(
        f"/api/v1/billing/refunds/{asked.json()['id']}/reject",
        json={},
        headers=bearer(session, run_id, "admin"),
    )

    assert too_much.status_code == 422
    assert no_reason.status_code == 422
