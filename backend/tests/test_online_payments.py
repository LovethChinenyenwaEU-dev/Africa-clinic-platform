"""Week 10 Step 5: Paystack behind an adapter; a signed webhook never pays twice (FR-B4)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.audit.service import SYSTEM_ACTOR_ID, list_audit_events
from app.modules.billing import online
from app.modules.billing.gateway import FakeGateway, GatewayResult, GatewayUnavailableError
from app.modules.billing.invoices import add_line, issue_invoice, start_invoice, view_invoice
from app.modules.billing.online import (
    BadSignatureError,
    InvalidOnlinePaymentError,
    OnlinePaymentNotAllowedError,
    check_online_payment,
    handle_webhook,
    start_online_payment,
)
from app.modules.billing.payments import InvalidPaymentError, record_payment
from app.modules.billing.prices import add_price
from app.modules.billing.refunds import InvalidRefundError, request_refund
from app.modules.identity.service import create_staff, login
from tests.scheduling_helpers import PASSWORD, book, build_clinic

CONSULT = 500_000  # 5,000 naira


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(online, "payment_gateway", lambda: fake)
    return fake


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


@pytest.fixture
def clinics(session, run_id, gateway):
    """Two clinics, each with an issued 5,000 naira invoice, nothing paid."""
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
        clinic["visit"] = visit
        clinic["invoice"] = invoice
        data[label] = clinic
    return data


def link(session, clinic, **extra):
    return start_online_payment(session, **who(clinic), invoice_id=clinic["invoice"].id, **extra)


def webhook_body(reference, event="charge.success"):
    return json.dumps({"event": event, "data": {"reference": reference}}).encode()


def paystack_says(gateway, reference, status="success", amount=CONSULT, currency="NGN"):
    gateway.outcomes[reference] = GatewayResult(status, amount, currency, "trx-1")


def send_webhook(session, gateway, reference, event="charge.success"):
    body = webhook_body(reference, event)
    return handle_webhook(session, body=body, signature=gateway.sign(body))


def money(session, clinic):
    view = view_invoice(session, **who(clinic), invoice_id=clinic["invoice"].id)
    return view.payment_status.value, view.paid_kobo, view.balance_kobo, view.credit_kobo


def actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [e for e in events if e.action.startswith("online_payment.")]


# --- payment links -----------------------------------------------------------------------


def test_a_link_is_for_what_is_owed_and_tells_the_gateway_nothing_personal(
    session, clinics, gateway
):
    a = clinics["a"]

    row = link(session, a)

    assert row.amount_kobo == CONSULT
    assert row.status == "pending"
    assert row.reference.startswith("LFY-")
    assert row.link == f"https://pay.invalid/{row.reference}"
    assert row.email == settings.payment_fallback_email
    sent = gateway.initialized[0]
    assert sent == {
        "reference": row.reference,
        "amount_kobo": CONSULT,
        "email": settings.payment_fallback_email,
        "invoice_number": "INV-000001",  # no names, no health details
    }
    assert [(e.action, e.patient_id) for e in actions(session, a)] == [
        ("online_payment.start", a["patient"].id)
    ]


def test_asking_again_gives_the_same_link_unless_the_amount_differs(session, clinics, gateway):
    a = clinics["a"]
    first = link(session, a)
    again = link(session, a)
    part = link(session, a, amount_kobo=200_000, email="ada@example.com")

    assert again.id == first.id
    assert part.id != first.id
    assert part.email == "ada@example.com"
    assert len(gateway.initialized) == 2


def test_links_only_for_money_still_owed(session, clinics):
    a = clinics["a"]
    second_visit = book(session, a, starts_at=a["visit"].starts_at.replace(hour=11))
    draft = start_invoice(session, **who(a), appointment_id=second_visit.id)

    with pytest.raises(OnlinePaymentNotAllowedError):
        start_online_payment(session, **who(a), invoice_id=draft.id)
    with pytest.raises(InvalidOnlinePaymentError):
        link(session, a, amount_kobo=CONSULT + 1)
    with pytest.raises(InvalidOnlinePaymentError):
        link(session, a, amount_kobo=0)
    with pytest.raises(InvalidOnlinePaymentError):
        link(session, a, email="not an email")
    record_payment(
        session, **who(a), invoice_id=a["invoice"].id, method="cash", amount_kobo=CONSULT
    )
    with pytest.raises(OnlinePaymentNotAllowedError):
        link(session, a)


def test_a_gateway_that_is_down_saves_nothing(session, clinics, gateway):
    a = clinics["a"]
    gateway.unreachable = True

    with pytest.raises(GatewayUnavailableError):
        link(session, a)

    assert actions(session, a) == []


# --- the webhook -------------------------------------------------------------------------


def test_a_confirmed_payment_is_recorded_once_however_often_the_webhook_comes(
    session, clinics, gateway
):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference)

    first = send_webhook(session, gateway, row.reference)
    second = send_webhook(session, gateway, row.reference)
    check_online_payment(session, **who(a), online_id=row.id)  # and a "check now" too

    view = view_invoice(session, **who(a), invoice_id=a["invoice"].id)
    assert first.startswith("succeeded")
    assert second.startswith("succeeded")
    assert [(p.method, p.amount_kobo, p.receipt_number) for p in view.payments] == [
        ("paystack", CONSULT, "RCT-000001")
    ]
    assert view.payments[0].received_by_id == a["desk"].id  # who sent the link
    assert view.online_payments[0].payment_id == view.payments[0].id
    assert money(session, a) == ("paid", CONSULT, 0, 0)
    paid = [e for e in actions(session, a) if e.action == "online_payment.paid"]
    assert [e.actor_id for e in paid] == [SYSTEM_ACTOR_ID]


def test_an_unsigned_or_wrongly_signed_webhook_is_refused(session, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference)
    body = webhook_body(row.reference)

    with pytest.raises(BadSignatureError):
        handle_webhook(session, body=body, signature=None)
    with pytest.raises(BadSignatureError):
        handle_webhook(session, body=body, signature="0" * 128)

    assert money(session, a) == ("unpaid", 0, CONSULT, 0)


def test_the_webhook_is_only_a_hint_the_gateways_answer_decides(session, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)
    # The webhook says success, but asked directly the gateway says it is still pending.

    outcome = send_webhook(session, gateway, row.reference)

    assert outcome.startswith("pending")
    assert money(session, a) == ("unpaid", 0, CONSULT, 0)


@pytest.mark.parametrize(
    ("amount", "currency"), [(CONSULT - 100, "NGN"), (CONSULT, "USD")]
)
def test_a_wrong_amount_or_currency_is_not_counted(session, clinics, gateway, amount, currency):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference, amount=amount, currency=currency)

    send_webhook(session, gateway, row.reference)

    failed = view_invoice(session, **who(a), invoice_id=a["invoice"].id).online_payments[0]
    assert failed.status == "failed"
    assert "Check it with the gateway" in (failed.failure_reason or "")
    assert money(session, a) == ("unpaid", 0, CONSULT, 0)


def test_a_declined_payment_is_marked_failed(session, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference, status="failed")

    send_webhook(session, gateway, row.reference)

    assert view_invoice(session, **who(a), invoice_id=a["invoice"].id).online_payments[
        0
    ].status == "failed"
    assert "online_payment.failed" in [e.action for e in actions(session, a)]


def test_other_events_and_unknown_references_are_ignored(session, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference)

    assert send_webhook(session, gateway, row.reference, event="transfer.success").startswith(
        "ignored"
    )
    assert send_webhook(session, gateway, "LFY-not-ours").startswith("ignored")
    assert money(session, a) == ("unpaid", 0, CONSULT, 0)


def test_check_now_records_a_payment_whose_webhook_was_lost(session, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)

    # Read the status at once: both answers are the same row object in this session,
    # so after the second check the first one would say "succeeded" too.
    first_status = check_online_payment(session, **who(a, "billing"), online_id=row.id).status
    paystack_says(gateway, row.reference)
    done = check_online_payment(session, **who(a, "billing"), online_id=row.id)

    assert first_status == "pending"
    assert done.status == "succeeded"
    assert [e.action for e in actions(session, a)].count("online_payment.check") == 1
    paid = [e for e in actions(session, a) if e.action == "online_payment.paid"]
    assert [e.actor_id for e in paid] == [a["billing"].id]


def test_money_that_arrives_after_the_bill_was_settled_shows_as_overpaid(
    session, clinics, gateway
):
    a = clinics["a"]
    row = link(session, a)
    record_payment(
        session, **who(a), invoice_id=a["invoice"].id, method="cash", amount_kobo=CONSULT
    )
    paystack_says(gateway, row.reference)

    send_webhook(session, gateway, row.reference)

    # The money is real, so it is recorded; the clinic owes the patient 5,000 naira back.
    assert money(session, a) == ("overpaid", 2 * CONSULT, 0, CONSULT)


def test_staff_cannot_type_in_an_online_payment_or_refund_one_online(session, clinics, gateway):
    a = clinics["a"]
    with pytest.raises(InvalidPaymentError):
        record_payment(
            session, **who(a), invoice_id=a["invoice"].id, method="paystack", amount_kobo=100
        )
    row = link(session, a)
    paystack_says(gateway, row.reference)
    send_webhook(session, gateway, row.reference)
    payment = view_invoice(session, **who(a), invoice_id=a["invoice"].id).payments[0]

    with pytest.raises(InvalidRefundError):
        request_refund(
            session,
            **who(a),
            payment_id=payment.id,
            amount_kobo=100,
            method="paystack",
            reason="Back to the card",
        )


def test_another_clinics_link_is_not_found(session, clinics):
    theirs = link(session, clinics["b"])

    with pytest.raises(online.OnlinePaymentNotFoundError):
        check_online_payment(session, **who(clinics["a"]), online_id=theirs.id)


# --- the doors ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, role, label="a"):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_payment_links_and_the_webhook_through_the_api(client, session, run_id, clinics, gateway):
    a = clinics["a"]
    url = f"/api/v1/billing/invoices/{a['invoice'].id}/online-payments"
    webhook = "/api/v1/billing/paystack/webhook"

    by_nurse = client.post(url, json={}, headers=bearer(session, run_id, "nurse"))
    made = client.post(url, json={}, headers=bearer(session, run_id, "billing"))
    reference = made.json()["reference"]
    body = webhook_body(reference)
    paystack_says(gateway, reference)
    unsigned = client.post(webhook, content=body)
    gateway.unreachable = True
    gateway_down = client.post(
        webhook, content=body, headers={"x-paystack-signature": gateway.sign(body)}
    )
    gateway.unreachable = False
    signed = client.post(
        webhook, content=body, headers={"x-paystack-signature": gateway.sign(body)}
    )
    invoice = client.get(
        f"/api/v1/billing/invoices/{a['invoice'].id}", headers=bearer(session, run_id, "billing")
    ).json()

    assert by_nurse.status_code == 403
    assert made.status_code == 201
    assert made.json()["link"].startswith("https://pay.invalid/")
    assert unsigned.status_code == 401
    assert gateway_down.status_code == 503  # Paystack will send it again
    assert signed.status_code == 200
    assert invoice["payment_status"] == "paid"
    assert [o["status"] for o in invoice["online_payments"]] == ["succeeded"]


def test_check_now_through_the_api(client, session, run_id, clinics, gateway):
    a = clinics["a"]
    row = link(session, a)
    paystack_says(gateway, row.reference)

    checked = client.post(
        f"/api/v1/billing/online-payments/{row.id}/check",
        headers=bearer(session, run_id, "front_desk"),
    )
    elsewhere = client.post(
        f"/api/v1/billing/online-payments/{row.id}/check",
        headers=bearer(session, run_id, "front_desk", label="b"),
    )

    assert checked.status_code == 200
    assert checked.json()["status"] == "succeeded"
    assert elsewhere.status_code == 404
