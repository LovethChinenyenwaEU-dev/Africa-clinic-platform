from fastapi import Depends, FastAPI

from app.main import app
from app.modules.identity.dependencies import get_current_staff

# Doors that are public on purpose. Adding a line here is a decision, so think first.
PUBLIC_OPERATIONS = {
    ("POST", "/api/v1/auth/login"),
    # A patient signs in with an SMS code: they cannot have a token before (Week 9).
    ("POST", "/api/v1/patient-portal/sign-in/start"),
    ("POST", "/api/v1/patient-portal/sign-in/finish"),
    # Paystack tells us a payment went through. It cannot sign in; its HMAC signature
    # is checked instead, and nothing is believed until the gateway confirms (Week 10).
    ("POST", "/api/v1/billing/paystack/webhook"),
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PREFIX = "/api/v1"


def list_operations(application, prefix=PREFIX):
    """Every (method, path, details) the app officially offers under the prefix."""
    found = []
    for path, operations in application.openapi()["paths"].items():
        if not path.startswith(prefix):
            continue
        for method, details in operations.items():
            if method in HTTP_METHODS:
                found.append((method.upper(), path, details))
    return found


def find_unguarded(application, public=frozenset()) -> list[str]:
    """Doors that show no login requirement and are not public on purpose."""
    return sorted(
        f"{method} {path}"
        for method, path, details in list_operations(application)
        if (method, path) not in public and not details.get("security")
    )


def test_every_api_route_is_guarded_unless_public_on_purpose():
    assert find_unguarded(app, public=PUBLIC_OPERATIONS) == []


def test_public_routes_list_is_not_stale():
    existing = {(method, path) for method, path, _ in list_operations(app)}
    assert PUBLIC_OPERATIONS <= existing


def test_the_checker_can_see_our_real_doors():
    """The test button: if this fails, the alarm is blind."""
    existing = {(method, path) for method, path, _ in list_operations(app)}
    assert ("GET", "/api/v1/auth/me") in existing
    assert ("POST", "/api/v1/tenancy/branches") in existing
    assert ("GET", "/api/v1/staff") in existing


def test_the_checker_really_catches_an_unguarded_route():
    """Another test button: build a tiny app with one open door and one locked door."""
    sample = FastAPI()

    @sample.get("/api/v1/oops")
    def open_door():
        return {}

    @sample.get("/api/v1/fine", dependencies=[Depends(get_current_staff)])
    def locked_door():
        return {}

    assert find_unguarded(sample) == ["GET /api/v1/oops"]