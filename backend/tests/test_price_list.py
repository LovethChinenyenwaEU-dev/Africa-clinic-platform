"""Week 10 Step 1: the clinic's price list (services and prices, in kobo)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.billing.prices import (
    InvalidPriceError,
    PriceNameTakenError,
    PriceNotFoundError,
    add_price,
    change_price,
    list_prices,
)
from app.modules.identity.service import create_staff, login
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
CONSULT = 500_000  # 5,000 naira


def build_clinic(session, run_id, label):
    tenant = create_tenant(session, name=f"Clinic {label} {run_id}")
    people = {
        role: create_staff(
            session,
            tenant_id=tenant.id,
            email=f"{label}-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
        for role in ("admin", "billing", "front_desk", "nurse")
    }
    return {"tenant": tenant, **people}


@pytest.fixture
def clinics(session, run_id):
    return {label: build_clinic(session, run_id, label) for label in ("a", "b")}


def by_admin(clinic):
    return {"tenant_id": clinic["tenant"].id, "actor_id": clinic["admin"].id}


def add(session, clinic, name="GP consultation", price_kobo=CONSULT, **changes):
    return add_price(session, **by_admin(clinic), name=name, price_kobo=price_kobo, **changes)


def change(session, clinic, row, **changes):
    values = {
        "name": row.name,
        "code": row.code,
        "price_kobo": row.price_kobo,
        "active": row.active,
    }
    return change_price(session, **by_admin(clinic), price_id=row.id, **(values | changes))


def price_lines(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return sorted((e.action, e.entity_id) for e in events if e.action.startswith("price."))


def names(rows):
    return [row.name for row in rows]


# --- the service ---------------------------------------------------------------


def test_an_admin_adds_services_and_the_list_reads_a_to_z(session, clinics):
    a = clinics["a"]
    malaria = add(session, a, name="  Malaria   test ", price_kobo=150_000, code=" mrdt ")
    consult = add(session, a)

    assert malaria.name == "Malaria test"  # spaces tidied
    assert malaria.code == "MRDT"
    assert malaria.price_kobo == 150_000
    assert names(list_prices(session, tenant_id=a["tenant"].id)) == [
        "GP consultation",
        "Malaria test",
    ]
    assert price_lines(session, a) == sorted(
        [("price.add", malaria.id), ("price.add", consult.id)]
    )


def test_a_repeated_send_adds_the_service_once(session, clinics):
    a = clinics["a"]
    price_id = uuid.uuid4()

    first = add(session, a, price_id=price_id)
    again = add(session, a, price_id=price_id)

    assert again.id == first.id == price_id
    assert len(list_prices(session, tenant_id=a["tenant"].id)) == 1
    assert len(price_lines(session, a)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "   "},
        {"name": "x" * 121},
        {"code": "C" * 21},
        {"price_kobo": -1},
        {"price_kobo": 1_000_000_001},
        {"price_kobo": True},
        {"price_kobo": 12.5},
    ],
)
def test_bad_services_are_refused_and_nothing_is_saved(session, clinics, changes):
    a = clinics["a"]

    with pytest.raises(InvalidPriceError):
        add(session, a, **changes)

    assert list_prices(session, tenant_id=a["tenant"].id, include_retired=True) == []
    assert price_lines(session, a) == []


def test_a_free_service_is_allowed(session, clinics):
    assert add(session, clinics["a"], name="Health talk", price_kobo=0).price_kobo == 0


def test_two_active_services_never_share_a_name(session, clinics):
    a = clinics["a"]
    add(session, a)

    with pytest.raises(PriceNameTakenError):
        add(session, a, name="gp CONSULTATION")


def test_another_clinic_may_use_the_same_name(session, clinics):
    add(session, clinics["a"])
    other = add(session, clinics["b"])

    assert other.tenant_id == clinics["b"]["tenant"].id


def test_a_price_change_is_saved_and_written_in_the_diary(session, clinics):
    a = clinics["a"]
    row = add(session, a)

    changed = change(session, a, row, price_kobo=650_000, code="cons")

    assert changed.price_kobo == 650_000
    assert changed.code == "CONS"
    assert changed.updated_by_id == a["admin"].id
    assert changed.updated_at is not None
    assert ("price.change", row.id) in price_lines(session, a)


def test_sending_the_same_values_changes_nothing(session, clinics):
    a = clinics["a"]
    row = add(session, a)

    change(session, a, row)

    assert price_lines(session, a) == [("price.add", row.id)]


def test_a_retired_service_leaves_the_list_and_frees_its_name(session, clinics):
    a = clinics["a"]
    old = add(session, a)

    change(session, a, old, active=False)
    new = add(session, a, price_kobo=600_000)  # same name, new price

    assert [row.id for row in list_prices(session, tenant_id=a["tenant"].id)] == [new.id]
    every = list_prices(session, tenant_id=a["tenant"].id, include_retired=True)
    assert {row.id for row in every} == {old.id, new.id}
    with pytest.raises(PriceNameTakenError):
        change(session, a, old, active=True)  # its name is taken again


def test_another_clinics_service_is_not_found(session, clinics):
    row = add(session, clinics["b"])

    with pytest.raises(PriceNotFoundError):
        change(session, clinics["a"], row, price_kobo=1)


# --- the doors -----------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def bearer(session, run_id, label, role):
    token = login(session, email=f"{label}-{role}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_only_an_admin_adds_or_changes_prices(client, session, run_id, clinics):
    url = "/api/v1/billing/prices"
    body = {"name": "GP consultation", "code": "cons", "price_kobo": CONSULT}

    for role in ("front_desk", "billing", "nurse"):
        refused = client.post(url, json=body, headers=bearer(session, run_id, "a", role))
        assert refused.status_code == 403
    added = client.post(url, json=body, headers=bearer(session, run_id, "a", "admin"))
    assert added.status_code == 201
    row = added.json()
    assert (row["name"], row["code"], row["price_kobo"], row["active"]) == (
        "GP consultation",
        "CONS",
        CONSULT,
        True,
    )

    change_url = f"/api/v1/billing/prices/{row['id']}"
    retire = {"name": "GP consultation", "code": "CONS", "price_kobo": CONSULT, "active": False}
    refused = client.post(change_url, json=retire, headers=bearer(session, run_id, "a", "billing"))
    retired = client.post(change_url, json=retire, headers=bearer(session, run_id, "a", "admin"))
    assert refused.status_code == 403
    assert retired.status_code == 200
    assert retired.json()["active"] is False


def test_everyone_who_books_or_bills_reads_the_list(client, session, run_id, clinics):
    add(session, clinics["a"])
    add(session, clinics["b"], name="Other clinic's service")

    for role in ("admin", "billing", "front_desk", "nurse"):
        response = client.get("/api/v1/billing/prices", headers=bearer(session, run_id, "a", role))
        assert response.status_code == 200
        assert [row["name"] for row in response.json()] == ["GP consultation"]


def test_the_doors_answer_with_clear_errors(client, session, run_id, clinics):
    admin = bearer(session, run_id, "a", "admin")
    add(session, clinics["a"])
    others = add(session, clinics["b"])
    url = "/api/v1/billing/prices"

    taken = client.post(url, json={"name": "gp consultation", "price_kobo": 1}, headers=admin)
    negative = client.post(url, json={"name": "X-ray", "price_kobo": -5}, headers=admin)
    in_naira = client.post(url, json={"name": "X-ray", "price_kobo": "5000.50"}, headers=admin)
    elsewhere = client.post(
        f"{url}/{others.id}",
        json={"name": "Mine now", "price_kobo": 1, "active": True},
        headers=admin,
    )

    assert taken.status_code == 409
    assert negative.status_code == 422
    assert in_naira.status_code == 422  # whole kobo only, never text or fractions
    assert elsewhere.status_code == 404
