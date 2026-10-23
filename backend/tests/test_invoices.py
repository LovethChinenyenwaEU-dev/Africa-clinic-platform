"""Week 10 Step 2: invoices, one per visit, built from the price list (FR-B1)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing.invoices import (
    InvalidInvoiceError,
    InvoiceLockedError,
    InvoiceNotFoundError,
    add_line,
    issue_invoice,
    list_patient_invoices,
    remove_line,
    start_invoice,
    view_invoice,
    void_invoice,
)
from app.modules.billing.prices import add_price, change_price
from app.modules.identity.service import create_staff, login
from app.modules.scheduling.lifecycle import cancel_appointment
from tests.scheduling_helpers import PASSWORD, book, build_clinic

CONSULT = 500_000  # 5,000 naira
MALARIA_TEST = 150_000  # 1,500 naira


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
        admin = {"tenant_id": clinic["tenant"].id, "actor_id": clinic["admin"].id}
        clinic["consult"] = add_price(session, **admin, name="GP consultation", price_kobo=CONSULT)
        clinic["malaria"] = add_price(
            session, **admin, name="Malaria test", price_kobo=MALARIA_TEST
        )
        clinic["visit"] = book(session, clinic)
        data[label] = clinic
    return data


def who(clinic, person="desk"):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic[person].id}


def start(session, clinic, person="desk", **extra):
    return start_invoice(session, **who(clinic, person), appointment_id=clinic["visit"].id, **extra)


def add(session, clinic, invoice, service="consult", quantity=1, **extra):
    return add_line(
        session,
        **who(clinic),
        invoice_id=invoice.id,
        price_item_id=clinic[service].id,
        quantity=quantity,
        **extra,
    )


def issue(session, clinic, invoice):
    return issue_invoice(session, **who(clinic), invoice_id=invoice.id)


def invoice_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [e for e in events if e.action.startswith("invoice.")]


# --- drafts ----------------------------------------------------------------------


def test_a_draft_is_built_from_the_price_list(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)

    add(session, a, invoice)
    result = add(session, a, invoice, service="malaria", quantity=2)

    assert result.invoice.status == "draft"
    assert result.invoice.number is None
    assert result.invoice.patient_id == a["patient"].id
    rows = [(x.description, x.unit_price_kobo, x.quantity, x.amount_kobo) for x in result.lines]
    assert rows == [
        ("GP consultation", CONSULT, 1, CONSULT),
        ("Malaria test", MALARIA_TEST, 2, 2 * MALARIA_TEST),
    ]
    assert result.invoice.total_kobo == CONSULT + 2 * MALARIA_TEST
    lines = invoice_lines(session, a)
    assert sorted(e.action for e in lines) == [
        "invoice.create",
        "invoice.line_add",
        "invoice.line_add",
    ]
    assert {e.patient_id for e in lines} == {a["patient"].id}


def test_a_later_price_change_never_changes_a_line(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    add(session, a, invoice)

    service = a["consult"]
    change_price(
        session,
        **who(a, "admin"),
        price_id=service.id,
        name="GP consultation (new)",
        code=None,
        price_kobo=900_000,
        active=True,
    )
    result = view_invoice(session, **who(a), invoice_id=invoice.id)

    assert [(x.description, x.amount_kobo) for x in result.lines] == [("GP consultation", CONSULT)]


def test_a_visit_has_one_invoice_and_a_repeat_send_makes_one(session, clinics):
    a = clinics["a"]
    chosen = uuid.uuid4()

    first = start(session, a, invoice_id=chosen)
    again = start(session, a, invoice_id=chosen)
    other_person = start(session, a, person="billing")

    assert first.id == again.id == other_person.id == chosen
    assert [e.action for e in invoice_lines(session, a)] == ["invoice.create"]


def test_a_line_sent_twice_is_added_once(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    line_id = uuid.uuid4()

    add(session, a, invoice, line_id=line_id)
    result = add(session, a, invoice, line_id=line_id)

    assert [x.id for x in result.lines] == [line_id]
    assert result.invoice.total_kobo == CONSULT


def test_a_cancelled_or_unknown_visit_is_not_billed(session, clinics):
    a = clinics["a"]
    cancel_appointment(session, **who(a), appointment_id=a["visit"].id)

    with pytest.raises(InvalidInvoiceError):
        start(session, a)
    with pytest.raises(InvoiceNotFoundError):
        start_invoice(session, **who(a), appointment_id=uuid.uuid4())
    with pytest.raises(InvoiceNotFoundError):  # another clinic's visit
        start_invoice(session, **who(a), appointment_id=clinics["b"]["visit"].id)


@pytest.mark.parametrize("quantity", [0, 101, True, 1.5])
def test_a_bad_quantity_is_refused(session, clinics, quantity):
    a = clinics["a"]
    invoice = start(session, a)

    with pytest.raises(InvalidInvoiceError):
        add(session, a, invoice, quantity=quantity)


def test_only_current_services_of_this_clinic_can_be_added(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    service = a["malaria"]
    change_price(
        session,
        **who(a, "admin"),
        price_id=service.id,
        name=service.name,
        code=None,
        price_kobo=service.price_kobo,
        active=False,
    )

    with pytest.raises(InvalidInvoiceError):
        add(session, a, invoice, service="malaria")
    with pytest.raises(InvoiceNotFoundError):
        add_line(
            session,
            **who(a),
            invoice_id=invoice.id,
            price_item_id=clinics["b"]["consult"].id,
        )


def test_removing_a_line_lowers_the_total(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    add(session, a, invoice)
    with_test = add(session, a, invoice, service="malaria")
    malaria_line = with_test.lines[1]

    result = remove_line(session, **who(a), invoice_id=invoice.id, line_id=malaria_line.id)

    assert [x.description for x in result.lines] == ["GP consultation"]
    assert result.invoice.total_kobo == CONSULT
    assert "invoice.line_remove" in [e.action for e in invoice_lines(session, a)]


def test_a_line_of_another_invoice_cannot_be_removed(session, clinics):
    a, b = clinics["a"], clinics["b"]
    mine = start(session, a)
    theirs = start(session, b)
    their_line = add(session, b, theirs).lines[0]

    with pytest.raises(InvoiceNotFoundError):
        remove_line(session, **who(a), invoice_id=mine.id, line_id=their_line.id)


# --- issuing and voiding ---------------------------------------------------------


def test_an_empty_invoice_is_not_issued(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)

    with pytest.raises(InvalidInvoiceError):
        issue(session, a, invoice)


def test_issuing_numbers_the_invoice_in_order_per_clinic(session, clinics):
    a, b = clinics["a"], clinics["b"]
    first = start(session, a)
    add(session, a, first)
    second_visit = book(session, a, starts_at=a["visit"].starts_at.replace(hour=11))
    second = start_invoice(session, **who(a), appointment_id=second_visit.id)
    add(session, a, second, service="malaria")
    other_clinic = start(session, b)
    add(session, b, other_clinic)

    one = issue(session, a, first)
    two = issue(session, a, second)
    theirs = issue(session, b, other_clinic)
    again = issue(session, a, first)  # pressing "issue" twice

    assert (one.invoice.number, two.invoice.number) == ("INV-000001", "INV-000002")
    assert theirs.invoice.number == "INV-000001"  # each clinic counts its own
    assert again.invoice.number == "INV-000001"
    assert one.invoice.status == "issued"
    assert one.invoice.issued_by_id == a["desk"].id
    assert one.invoice.total_kobo == CONSULT
    issued = [e for e in invoice_lines(session, a) if e.action == "invoice.issue"]
    assert len(issued) == 2  # the second press wrote nothing


def test_an_issued_invoice_is_frozen(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    line = add(session, a, invoice).lines[0]
    issue(session, a, invoice)

    with pytest.raises(InvoiceLockedError):
        add(session, a, invoice, service="malaria")
    with pytest.raises(InvoiceLockedError):
        remove_line(session, **who(a), invoice_id=invoice.id, line_id=line.id)
    with pytest.raises(InvoiceLockedError):
        void_invoice(session, **who(a), invoice_id=invoice.id, reason="Changed my mind")
    assert start(session, a).id == invoice.id  # the visit stays billed by it


def test_a_voided_draft_keeps_its_reason_and_the_visit_can_be_billed_again(session, clinics):
    a = clinics["a"]
    draft = start(session, a)
    add(session, a, draft)

    with pytest.raises(InvalidInvoiceError):
        void_invoice(session, **who(a), invoice_id=draft.id, reason=" no ")
    voided = void_invoice(session, **who(a), invoice_id=draft.id, reason="Wrong   patient's visit")
    fresh = start(session, a)

    assert voided.invoice.status == "void"
    assert voided.invoice.void_reason == "Wrong patient's visit"
    assert voided.invoice.voided_by_id == a["desk"].id
    assert fresh.id != draft.id
    with pytest.raises(InvoiceLockedError):
        issue(session, a, voided.invoice)


# --- reading ----------------------------------------------------------------------


def test_reading_invoices_is_written_in_the_diary(session, clinics):
    a = clinics["a"]
    invoice = start(session, a)

    view_invoice(session, **who(a, "billing"), invoice_id=invoice.id)
    listed = list_patient_invoices(session, **who(a, "billing"), patient_id=a["patient"].id)

    assert [row.id for row in listed] == [invoice.id]
    reads = [
        (e.action, e.actor_id, e.patient_id)
        for e in invoice_lines(session, a)
        if e.action in ("invoice.view", "invoice.list")
    ]
    assert sorted(reads) == [
        ("invoice.list", a["billing"].id, a["patient"].id),
        ("invoice.view", a["billing"].id, a["patient"].id),
    ]


def test_another_clinics_invoice_and_patient_are_not_found(session, clinics):
    theirs = start(session, clinics["b"])

    with pytest.raises(InvoiceNotFoundError):
        view_invoice(session, **who(clinics["a"]), invoice_id=theirs.id)
    with pytest.raises(InvoiceNotFoundError):
        list_patient_invoices(
            session, **who(clinics["a"]), patient_id=clinics["b"]["patient"].id
        )


# --- the doors --------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_billing_builds_and_issues_an_invoice_through_the_api(client, session, run_id, clinics):
    a = clinics["a"]
    billing = bearer(session, run_id, "a", "billing")
    visit_url = f"/api/v1/billing/visits/{a['visit'].id}/invoice"

    before = client.get(visit_url, headers=billing)
    started = client.post(
        "/api/v1/billing/invoices", json={"appointment_id": str(a["visit"].id)}, headers=billing
    )
    invoice_url = f"/api/v1/billing/invoices/{started.json()['id']}"
    added = client.post(
        f"{invoice_url}/lines",
        json={"price_item_id": str(a["malaria"].id), "quantity": 2},
        headers=billing,
    )
    as_text = client.post(
        f"{invoice_url}/lines",
        json={"price_item_id": str(a["consult"].id), "quantity": "2"},
        headers=billing,
    )
    issued = client.post(f"{invoice_url}/issue", headers=billing)
    too_late = client.post(
        f"{invoice_url}/lines", json={"price_item_id": str(a["consult"].id)}, headers=billing
    )
    after = client.get(visit_url, headers=billing)
    listed = client.get(f"/api/v1/billing/patients/{a['patient'].id}/invoices", headers=billing)

    assert before.status_code == 404
    assert started.status_code == 201
    assert started.json()["status"] == "draft"
    assert added.status_code == 201
    assert added.json()["total_kobo"] == 2 * MALARIA_TEST
    assert as_text.status_code == 422  # whole numbers only
    assert issued.status_code == 200
    assert (issued.json()["status"], issued.json()["number"]) == ("issued", "INV-000001")
    assert too_late.status_code == 409
    assert after.json()["lines"][0]["description"] == "Malaria test"
    assert [row["number"] for row in listed.json()] == ["INV-000001"]


def test_only_front_desk_and_billing_change_invoices(client, session, run_id, clinics):
    a = clinics["a"]
    invoice = start(session, a)
    body = {"appointment_id": str(a["visit"].id)}
    read_url = f"/api/v1/billing/invoices/{invoice.id}"

    for role in ("nurse", "doctor", "admin"):
        headers = bearer(session, run_id, "a", role)
        refused = client.post("/api/v1/billing/invoices", json=body, headers=headers)
        assert refused.status_code == 403
    for role in ("nurse", "doctor"):
        headers = bearer(session, run_id, "a", role)
        assert client.get(read_url, headers=headers).status_code == 403
    admin_reads = client.get(read_url, headers=bearer(session, run_id, "a", "admin"))
    desk_starts = client.post(
        "/api/v1/billing/invoices", json=body, headers=bearer(session, run_id, "a", "front_desk")
    )

    assert admin_reads.status_code == 200
    assert desk_starts.status_code == 201


def test_another_clinics_invoice_is_not_found_through_the_api(client, session, run_id, clinics):
    theirs = start(session, clinics["b"])
    billing = bearer(session, run_id, "a", "billing")

    read = client.get(f"/api/v1/billing/invoices/{theirs.id}", headers=billing)
    issue_it = client.post(f"/api/v1/billing/invoices/{theirs.id}/issue", headers=billing)

    assert read.status_code == 404
    assert issue_it.status_code == 404
