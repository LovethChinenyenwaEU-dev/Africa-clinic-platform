"""Landing step 2: the public "Register interest" form is saved, limited, and kept a year."""
import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlmodel import col, select

from app import cli
from app.main import app
from app.modules.outreach import service
from app.modules.outreach.models import InterestRequest
from app.modules.outreach.service import (
    Interest,
    TooManyRequestsError,
    interest_csv,
    purge_old_interest,
    submit_interest,
)

URL = "/api/v1/public/interest"
NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


@pytest.fixture
def domain(session, run_id):
    """A unique email domain for this test run; its rows are removed afterwards."""
    name = f"{run_id}.interest.example.com"
    yield name
    session.execute(
        delete(InterestRequest).where(col(InterestRequest.email).endswith(f"@{name}"))
    )
    session.commit()


def form(domain, **changes):
    return {
        "full_name": "Ada Obi",
        "email": f"ada@{domain}",
        "phone": "+234 803 000 0000",
        "organisation": "Sunrise Clinic",
        "role": "Clinical encounters",
        "message": "We want fewer paper folders.",
    } | changes


def saved(session, domain):
    return session.exec(
        select(InterestRequest).where(col(InterestRequest.email).endswith(f"@{domain}"))
    ).all()


def test_the_form_is_saved_and_says_nothing_back(session, domain):
    response = TestClient(app).post(URL, json=form(domain, email=f"  ADA@{domain.upper()} "))

    assert response.status_code == 201
    assert response.json() == {"received": True}
    rows = saved(session, domain)
    assert [(r.full_name, r.email, r.organisation) for r in rows] == [
        ("Ada Obi", f"ada@{domain}", "Sunrise Clinic")
    ]


def test_it_is_public_on_purpose():
    assert TestClient(app).post(URL, json={}).status_code == 422  # not 401


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"full_name": ""},
        {"organisation": ""},
        {"message": "x" * 2001},
    ],
)
def test_bad_forms_are_refused_and_nothing_is_saved(session, domain, changes):
    response = TestClient(app).post(URL, json=form(domain, **changes))

    assert response.status_code == 422
    assert saved(session, domain) == []


def test_one_address_may_send_three_a_day(session, domain):
    interest = Interest(**form(domain))
    for minute in range(3):
        submit_interest(session, interest, now=NOW + timedelta(minutes=minute))

    with pytest.raises(TooManyRequestsError):
        submit_interest(session, interest, now=NOW + timedelta(minutes=5))
    submit_interest(session, interest, now=NOW + timedelta(days=1, minutes=1))  # next day
    assert len(saved(session, domain)) == 4


def test_the_whole_form_has_an_hourly_limit(session, domain, monkeypatch):
    monkeypatch.setattr(service, "PER_HOUR", 2)
    for name in ("a", "b"):
        submit_interest(session, Interest(**form(domain, email=f"{name}@{domain}")), now=NOW)

    with pytest.raises(TooManyRequestsError):
        submit_interest(session, Interest(**form(domain, email=f"c@{domain}")), now=NOW)


def test_too_many_answers_429(session, domain, monkeypatch):
    monkeypatch.setattr(service, "PER_EMAIL_PER_DAY", 1)
    client = TestClient(app)

    assert client.post(URL, json=form(domain)).status_code == 201
    assert client.post(URL, json=form(domain)).status_code == 429


def test_requests_are_deleted_after_a_year(session, domain):
    submit_interest(session, Interest(**form(domain)), now=NOW - timedelta(days=366))
    submit_interest(session, Interest(**form(domain, email=f"b@{domain}")), now=NOW)

    purge_old_interest(session, now=NOW)

    assert [r.email for r in saved(session, domain)] == [f"b@{domain}"]


def test_the_owner_reads_them_as_csv(session, domain, capsys):
    submit_interest(session, Interest(**form(domain)), now=datetime.now(UTC))

    assert cli.main(["list-interest", "--days", "1"]) == 0

    rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert rows[0] == ["received", "name", "email", "phone", "organisation", "role", "message"]
    mine = [row for row in rows if row[2].endswith(domain)]
    assert [(row[2], row[4]) for row in mine] == [(f"ada@{domain}", "Sunrise Clinic")]


def test_the_csv_leaves_out_older_requests(session, domain):
    submit_interest(session, Interest(**form(domain)), now=NOW - timedelta(days=40))

    text = interest_csv(session, since=NOW - timedelta(days=30))

    assert domain not in text
