"""Week 11 Step 4: sign one device out, at once, without touching the others."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.audit.service import list_audit_events
from app.modules.identity.models import StaffSession
from app.modules.identity.service import create_staff, login
from app.modules.identity.sessions import describe_device
from app.modules.identity.tokens import create_access_token, decode_access_token
from app.modules.tenancy.service import create_tenant

PASSWORD = "a-long-enough-password"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
MY_DEVICES = "/api/v1/staff/me/sessions"
CHROME_ON_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinics(session, run_id):
    """Clinic A has an admin and a nurse. Clinic B has its own admin."""
    tenant_a = create_tenant(session, name=f"Devices A {run_id}")
    tenant_b = create_tenant(session, name=f"Devices B {run_id}")

    def person(tenant, name, role):
        return create_staff(
            session,
            tenant_id=tenant.id,
            email=f"dev-{name}@{run_id}.example.com",
            full_name=f"Test {name}",
            role=role,
            password=PASSWORD,
        )

    return {
        "admin": person(tenant_a, "admin", "admin"),
        "nurse": person(tenant_a, "nurse", "nurse"),
        "outsider": person(tenant_b, "outsider", "admin"),
    }


def sign_in(session, run_id, name):
    """One sign-in = one device. Returns its headers."""
    token = login(session, email=f"dev-{name}@{run_id}.example.com", password=PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def sid_of(headers):
    return decode_access_token(headers["Authorization"].removeprefix("Bearer ")).session_id


def test_every_token_names_its_sign_in(session, run_id, clinics):
    assert sid_of(sign_in(session, run_id, "nurse")) is not None


def test_a_token_without_a_sign_in_is_refused(client, clinics):
    nurse = clinics["nurse"]
    token = create_access_token(staff_id=nurse.id, tenant_id=nurse.tenant_id, role="nurse")

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_signing_out_stops_the_token_at_once(client, session, run_id, clinics):
    headers = sign_in(session, run_id, "nurse")
    assert client.get(ME_URL, headers=headers).status_code == 200

    response = client.post(LOGOUT_URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"signed_out": True}
    assert client.get(ME_URL, headers=headers).status_code == 401  # not 30 minutes later


def test_logout_needs_a_token(client):
    assert client.post(LOGOUT_URL).status_code == 401


def test_my_device_list_marks_the_one_asking(client, session, run_id, clinics):
    phone = sign_in(session, run_id, "nurse")
    laptop = sign_in(session, run_id, "nurse")

    devices = client.get(MY_DEVICES, headers=laptop).json()

    assert {d["id"] for d in devices} == {str(sid_of(phone)), str(sid_of(laptop))}
    current = [d for d in devices if d["current"]]
    assert [d["id"] for d in current] == [str(sid_of(laptop))]
    assert set(devices[0]) == {"id", "label", "created_at", "last_seen_at", "current"}


def test_ending_one_device_leaves_the_other_working(client, session, run_id, clinics):
    phone = sign_in(session, run_id, "nurse")
    laptop = sign_in(session, run_id, "nurse")

    response = client.post(f"{MY_DEVICES}/{sid_of(phone)}/end", headers=laptop)

    assert response.status_code == 200
    assert client.get(ME_URL, headers=phone).status_code == 401
    assert client.get(ME_URL, headers=laptop).status_code == 200
    ids = {d["id"] for d in client.get(MY_DEVICES, headers=laptop).json()}
    assert ids == {str(sid_of(laptop))}


def test_ending_a_device_is_written_in_the_diary(client, session, run_id, clinics):
    phone = sign_in(session, run_id, "nurse")
    laptop = sign_in(session, run_id, "nurse")

    client.post(f"{MY_DEVICES}/{sid_of(phone)}/end", headers=laptop)

    events = list_audit_events(session, tenant_id=clinics["nurse"].tenant_id)
    ends = [e for e in events if e.action == "session.end"]
    assert [(e.actor_id, e.entity_id) for e in ends] == [(clinics["nurse"].id, sid_of(phone))]


def test_nobody_ends_someone_elses_device_through_their_own_list(
    client, session, run_id, clinics
):
    nurse_phone = sign_in(session, run_id, "nurse")
    admin = sign_in(session, run_id, "admin")

    response = client.post(f"{MY_DEVICES}/{sid_of(nurse_phone)}/end", headers=admin)

    assert response.status_code == 404
    assert client.get(ME_URL, headers=nurse_phone).status_code == 200


def test_an_admin_sees_and_ends_a_staff_members_device(client, session, run_id, clinics):
    nurse_phone = sign_in(session, run_id, "nurse")
    admin = sign_in(session, run_id, "admin")
    nurse_id = clinics["nurse"].id

    devices = client.get(f"/api/v1/staff/{nurse_id}/sessions", headers=admin).json()
    assert [d["id"] for d in devices] == [str(sid_of(nurse_phone))]
    assert devices[0]["current"] is False

    response = client.post(
        f"/api/v1/staff/{nurse_id}/sessions/{sid_of(nurse_phone)}/end", headers=admin
    )

    assert response.status_code == 200
    assert client.get(ME_URL, headers=nurse_phone).status_code == 401
    events = list_audit_events(session, tenant_id=clinics["nurse"].tenant_id)
    ends = [e for e in events if e.action == "session.end"]
    assert [e.actor_id for e in ends] == [clinics["admin"].id]


def test_a_nurse_cannot_manage_other_peoples_devices(client, session, run_id, clinics):
    admin_laptop = sign_in(session, run_id, "admin")
    nurse = sign_in(session, run_id, "nurse")
    admin_id = clinics["admin"].id

    listed = client.get(f"/api/v1/staff/{admin_id}/sessions", headers=nurse)
    ended = client.post(
        f"/api/v1/staff/{admin_id}/sessions/{sid_of(admin_laptop)}/end", headers=nurse
    )

    assert listed.status_code == 403
    assert ended.status_code == 403
    assert client.get(ME_URL, headers=admin_laptop).status_code == 200


def test_another_clinic_gets_not_found(client, session, run_id, clinics):
    nurse_phone = sign_in(session, run_id, "nurse")
    outsider = sign_in(session, run_id, "outsider")
    nurse_id = clinics["nurse"].id

    listed = client.get(f"/api/v1/staff/{nurse_id}/sessions", headers=outsider)
    ended = client.post(
        f"/api/v1/staff/{nurse_id}/sessions/{sid_of(nurse_phone)}/end", headers=outsider
    )

    assert listed.status_code == 404
    assert ended.status_code == 404
    assert client.get(ME_URL, headers=nurse_phone).status_code == 200


def test_ending_an_already_ended_device_is_not_found(client, session, run_id, clinics):
    phone = sign_in(session, run_id, "nurse")
    laptop = sign_in(session, run_id, "nurse")
    url = f"{MY_DEVICES}/{sid_of(phone)}/end"

    client.post(url, headers=laptop)

    assert client.post(url, headers=laptop).status_code == 404


def test_switching_a_person_off_still_ends_every_device(client, session, run_id, clinics):
    nurse_phone = sign_in(session, run_id, "nurse")
    admin = sign_in(session, run_id, "admin")

    client.post(f"/api/v1/staff/{clinics['nurse'].id}/deactivate", headers=admin)

    assert client.get(ME_URL, headers=nurse_phone).status_code == 401


def test_the_device_name_comes_from_the_sign_in_request(client, session, run_id, clinics):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"dev-nurse@{run_id}.example.com", "password": PASSWORD},
        headers={"User-Agent": CHROME_ON_WINDOWS},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    devices = client.get(MY_DEVICES, headers=headers).json()

    assert [d["label"] for d in devices] == ["Chrome on Windows"]


@pytest.mark.parametrize(
    ("agent", "label"),
    [
        (CHROME_ON_WINDOWS, "Chrome on Windows"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604", "Safari on iPhone"),
        ("Mozilla/5.0 (Linux; Android 14) Chrome/129.0 Mobile Safari/537.36", "Chrome on Android"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0; rv:131.0) Firefox/131.0", "Firefox on Mac"),
        ("Mozilla/5.0 (Windows NT 10.0) Chrome/129.0 Safari/537.36 Edg/129.0", "Edge on Windows"),
        (None, "Unknown device"),
        ("", "Unknown device"),
        ("<script>", "script"),
    ],
)
def test_device_names_people_recognise(agent, label):
    assert describe_device(agent) == label


def test_an_expired_sign_in_is_refused_even_with_a_fresh_looking_token(
    client, session, run_id, clinics
):
    """The sign-in row has its own end time; the token cannot outlive it."""
    headers = sign_in(session, run_id, "nurse")
    row = session.get(StaffSession, sid_of(headers))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(row)
    session.commit()

    assert client.get(ME_URL, headers=headers).status_code == 401
