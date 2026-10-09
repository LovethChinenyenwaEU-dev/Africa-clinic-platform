import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import DEFAULT_SECRET_KEY, settings
from app.modules.identity.tokens import (
    ALGORITHM,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)

STAFF_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()


def make_token(**overrides):
    values = {"staff_id": STAFF_ID, "tenant_id": TENANT_ID, "role": "nurse"}
    values.update(overrides)
    return create_access_token(**values)


def test_token_carries_who_which_clinic_and_role():
    claims = decode_access_token(make_token())
    assert claims.staff_id == STAFF_ID
    assert claims.tenant_id == TENANT_ID
    assert claims.role == "nurse"


def test_expired_token_is_rejected():
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(InvalidTokenError):
        decode_access_token(make_token(now=two_hours_ago))


def test_token_with_a_forged_sticker_is_rejected():
    """Someone pretends to be an admin using their own secret key."""
    forged = jwt.encode(
        {
            "sub": str(STAFF_ID),
            "tenant_id": str(TENANT_ID),
            "role": "admin",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "some-other-secret-key-that-is-long-enough-0123",
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_garbage_is_rejected_without_crashing():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-token")


def test_default_secret_is_refused_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError):
        make_token()