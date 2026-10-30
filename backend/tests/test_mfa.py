"""Week 11 Step 3: admins and billing sign in with an authenticator app (FR-T4)."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity import totp
from app.modules.identity.mfa import (
    AlreadySetUpError,
    ChallengeError,
    LockedError,
    OwnResetError,
    WrongCodeError,
    begin_setup,
    confirm_setup,
    reset_mfa,
    start_sign_in,
    verify_sign_in,
)
from app.modules.identity.service import create_staff, login
from app.modules.identity.tokens import create_challenge_token
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
NOW = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def clinic(session, run_id):
    tenant = create_tenant(session, name=f"MFA clinic {run_id}")
    people = {
        role: create_staff(
            session,
            tenant_id=tenant.id,
            email=f"mfa-{role}@{run_id}.example.com",
            full_name=f"Test {role}",
            role=role,
            password=PASSWORD,
        )
        for role in ("admin", "billing", "nurse")
    }
    people["admin2"] = create_staff(
        session,
        tenant_id=tenant.id,
        email=f"mfa-admin2@{run_id}.example.com",
        full_name="Second admin",
        role="admin",
        password=PASSWORD,
    )
    return {"tenant": tenant, **people}


def email(run_id, who):
    return f"mfa-{who}@{run_id}.example.com"


def code(secret, when=NOW, steps_later=0):
    return totp.code_at(secret, totp.step_of(when.timestamp()) + steps_later)


def enrol(session, run_id, who="admin", when=NOW):
    """Password, set up the app, prove it with a first code. Answers the secret and codes."""
    step = start_sign_in(session, email=email(run_id, who), password=PASSWORD)
    secret = begin_setup(session, challenge_token=step.challenge_token).secret
    done = confirm_setup(
        session, challenge_token=step.challenge_token, code=code(secret, when), now=when
    )
    return secret, done.backup_codes


def challenge(session, run_id, who="admin"):
    return start_sign_in(session, email=email(run_id, who), password=PASSWORD).challenge_token


def bearer(session, run_id, who):
    token = login(session, email=email(run_id, who), password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def mfa_actions(session, clinic):
    events = list_audit_events(session, tenant_id=clinic["tenant"].id)
    return [e.action for e in events if e.action.startswith("mfa.")]


# --- who needs a second factor ----------------------------------------------------


def test_nurses_sign_in_with_a_password_only(session, run_id, clinic):
    step = start_sign_in(session, email=email(run_id, "nurse"), password=PASSWORD)

    assert step.access_token is not None
    assert step.mfa is None and step.challenge_token is None


@pytest.mark.parametrize("who", ["admin", "billing"])
def test_admins_and_billing_get_no_token_from_the_password_alone(session, run_id, clinic, who):
    first = start_sign_in(session, email=email(run_id, who), password=PASSWORD)

    assert first.access_token is None
    assert first.mfa == "setup"
    assert first.challenge_token

    enrol(session, run_id, who)
    later = start_sign_in(session, email=email(run_id, who), password=PASSWORD)
    assert (later.access_token, later.mfa) == (None, "verify")


# --- setting up the app -----------------------------------------------------------


def test_setting_up_gives_a_token_and_ten_backup_codes_once(session, run_id, clinic):
    _, backup_codes = enrol(session, run_id)

    assert len(backup_codes) == 10
    assert len(set(backup_codes)) == 10
    assert all(len(c) == 9 and c[4] == "-" for c in backup_codes)
    assert mfa_actions(session, clinic) == ["mfa.enroll"]
    with pytest.raises(AlreadySetUpError):
        begin_setup(session, challenge_token=challenge(session, run_id))


def test_a_wrong_first_code_does_not_set_up_the_app(session, run_id, clinic):
    token = challenge(session, run_id)
    secret = begin_setup(session, challenge_token=token).secret

    with pytest.raises(WrongCodeError):
        confirm_setup(session, challenge_token=token, code=code(secret, steps_later=5), now=NOW)

    assert start_sign_in(session, email=email(run_id, "admin"), password=PASSWORD).mfa == "setup"


# --- signing in with the app ------------------------------------------------------


def test_the_apps_next_code_signs_in_but_never_twice(session, run_id, clinic):
    secret, _ = enrol(session, run_id)
    later = NOW + timedelta(minutes=2)
    fresh = code(secret, later)

    token = verify_sign_in(
        session, challenge_token=challenge(session, run_id), code=fresh, now=later
    )

    assert token
    with pytest.raises(WrongCodeError):  # the same code again
        verify_sign_in(session, challenge_token=challenge(session, run_id), code=fresh, now=later)
    assert "mfa.verify" in mfa_actions(session, clinic)


def test_a_backup_code_works_once(session, run_id, clinic):
    _, backup_codes = enrol(session, run_id)
    spare = backup_codes[3].lower().replace("-", " ")  # typed loosely

    assert verify_sign_in(session, challenge_token=challenge(session, run_id), code=spare, now=NOW)
    with pytest.raises(WrongCodeError):
        verify_sign_in(session, challenge_token=challenge(session, run_id), code=spare, now=NOW)
    assert "mfa.backup_used" in mfa_actions(session, clinic)


def test_five_wrong_codes_lock_sign_in_for_fifteen_minutes(session, run_id, clinic):
    secret, _ = enrol(session, run_id)
    for _ in range(5):
        with pytest.raises(WrongCodeError):
            verify_sign_in(
                session, challenge_token=challenge(session, run_id), code="000000", now=NOW
            )

    soon = NOW + timedelta(minutes=5)
    with pytest.raises(LockedError):  # even the right code
        verify_sign_in(
            session, challenge_token=challenge(session, run_id), code=code(secret, soon), now=soon
        )
    after = NOW + timedelta(minutes=16)
    assert verify_sign_in(
        session, challenge_token=challenge(session, run_id), code=code(secret, after), now=after
    )
    assert mfa_actions(session, clinic).count("mfa.fail") == 5


def test_an_expired_or_wrong_kind_of_challenge_is_refused(session, run_id, clinic):
    enrol(session, run_id)
    old = create_challenge_token(
        staff_id=clinic["admin"].id,
        tenant_id=clinic["tenant"].id,
        now=datetime.now(UTC) - timedelta(minutes=6),
    )
    access = login(session, email=email(run_id, "admin"), password=PASSWORD)

    for bad in (old, access, "not-a-token"):
        with pytest.raises(ChallengeError):
            verify_sign_in(session, challenge_token=bad, code="123456", now=NOW)


# --- a lost phone -------------------------------------------------------------------


def test_another_admin_resets_a_lost_phone(session, run_id, clinic):
    enrol(session, run_id, "billing")
    tenant_id = clinic["tenant"].id

    with pytest.raises(OwnResetError):
        reset_mfa(
            session,
            tenant_id=tenant_id,
            actor_id=clinic["billing"].id,
            staff_id=clinic["billing"].id,
        )
    reset_mfa(
        session, tenant_id=tenant_id, actor_id=clinic["admin"].id, staff_id=clinic["billing"].id
    )

    assert start_sign_in(session, email=email(run_id, "billing"), password=PASSWORD).mfa == "setup"
    assert "mfa.reset" in mfa_actions(session, clinic)


# --- the doors ------------------------------------------------------------------------


def test_the_whole_sign_in_through_the_api(session, run_id, clinic):
    client = TestClient(app)
    password_step = client.post(
        "/api/v1/auth/login", json={"email": email(run_id, "admin"), "password": PASSWORD}
    )
    body = password_step.json()
    challenge_token = body["challenge_token"]

    as_staff = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {challenge_token}"}
    )
    setup = client.post("/api/v1/auth/mfa/setup", json={"challenge_token": challenge_token})
    secret = setup.json()["secret"]
    now = datetime.now(UTC)
    confirmed = client.post(
        "/api/v1/auth/mfa/confirm",
        json={"challenge_token": challenge_token, "code": code(secret, now)},
    )
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {confirmed.json()['access_token']}"}
    )
    again = client.post(
        "/api/v1/auth/login", json={"email": email(run_id, "admin"), "password": PASSWORD}
    ).json()
    verified = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": again["challenge_token"], "code": code(secret, now, 1)},
    )
    wrong = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": again["challenge_token"], "code": "000000"},
    )

    assert password_step.status_code == 200
    assert "access_token" not in body and body["mfa"] == "setup"
    assert as_staff.status_code == 401  # a challenge is not a staff token
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    assert confirmed.status_code == 200 and len(confirmed.json()["backup_codes"]) == 10
    assert me.json()["role"] == "admin"
    assert again["mfa"] == "verify"
    assert verified.status_code == 200 and verified.json()["access_token"]
    assert wrong.status_code == 401


def test_nurses_still_get_their_token_from_the_login_door(session, run_id, clinic):
    client = TestClient(app)

    answer = client.post(
        "/api/v1/auth/login", json={"email": email(run_id, "nurse"), "password": PASSWORD}
    ).json()

    assert answer["token_type"] == "bearer" and answer["access_token"]
    assert "mfa" not in answer


def test_the_reset_door_is_for_admins_and_not_for_ones_own_app(session, run_id, clinic):
    client = TestClient(app)
    enrol(session, run_id, "billing")
    admin = bearer(session, run_id, "admin")
    nurse = bearer(session, run_id, "nurse")
    url = f"/api/v1/staff/{clinic['billing'].id}/mfa/reset"

    by_nurse = client.post(url, headers=nurse)
    own = client.post(f"/api/v1/staff/{clinic['admin'].id}/mfa/reset", headers=admin)
    done = client.post(url, headers=admin)

    assert by_nurse.status_code == 403
    assert own.status_code == 403
    assert done.status_code == 200 and done.json() == {"reset": True}
