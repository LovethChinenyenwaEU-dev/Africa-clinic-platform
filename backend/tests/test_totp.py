"""The authenticator-app codes, checked against the RFCs' own examples."""
import pytest

from app.modules.identity import totp

# RFC 4226 / RFC 6238 test secret: the ASCII text "12345678901234567890", in base32.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


@pytest.mark.parametrize(
    ("counter", "code"),
    [(0, "755224"), (1, "287082"), (2, "359152"), (3, "969429"), (9, "520489")],
)
def test_rfc_4226_codes(counter, code):
    assert totp.code_at(RFC_SECRET, counter) == code


@pytest.mark.parametrize(
    ("unix_seconds", "code"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
    ],
)
def test_rfc_6238_codes(unix_seconds, code):
    assert totp.code_at(RFC_SECRET, totp.step_of(unix_seconds), digits=8) == code


def test_the_code_of_this_step_and_its_neighbours_is_accepted():
    now = 1_700_000_000.0
    step = totp.step_of(now)

    for nearby in (step - 1, step, step + 1):
        assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, nearby), now, None) == nearby
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + 2), now, None) is None
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step - 2), now, None) is None


def test_a_code_never_works_twice():
    now = 1_700_000_000.0
    step = totp.step_of(now)
    code = totp.code_at(RFC_SECRET, step)

    assert totp.matching_step(RFC_SECRET, code, now, after_step=step) is None
    assert totp.matching_step(RFC_SECRET, code, now, after_step=step - 1) == step


@pytest.mark.parametrize("typed", ["", "12345", "1234567", "abcdef", "12 34 5x"])
def test_anything_but_six_digits_is_refused(typed):
    assert totp.matching_step(RFC_SECRET, typed, 1_700_000_000.0, None) is None


def test_spaces_inside_a_code_are_fine():
    now = 1_700_000_000.0
    code = totp.code_at(RFC_SECRET, totp.step_of(now))

    assert totp.matching_step(RFC_SECRET, f"{code[:3]} {code[3:]}", now, None) is not None


def test_a_new_secret_and_its_link():
    secret = totp.new_secret()
    link = totp.provisioning_uri(secret, "admin@clinic.example")

    assert len(secret) == 32 and secret.isalnum() and secret == secret.upper()
    assert link.startswith("otpauth://totp/AfriPeak%20Health%3Aadmin%40clinic.example?")
    assert f"secret={secret}" in link
    assert "issuer=AfriPeak%20Health" in link
    assert totp.new_secret() != secret  # a fresh secret every time
