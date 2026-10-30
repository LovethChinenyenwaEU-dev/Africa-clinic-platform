"""Time-based one-time codes (TOTP, RFC 6238), as authenticator apps make them.

Written with the standard library only. The secret is 20 random bytes, shown to the
person once as base32 text (and as an otpauth:// link a phone can open). Every 30
seconds the app shows a new 6-digit code: HMAC-SHA1 of the 30-second step number,
cut down as RFC 4226 says. Tested against the RFC's own examples.
"""
import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
# Phone clocks drift: the step before and after are accepted too.
DRIFT_STEPS = 1


def new_secret() -> str:
    """20 random bytes as base32 text, without padding: what the person types or scans."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, step: int, digits: int = DIGITS) -> str:
    """The code for one 30-second step (RFC 4226 dynamic truncation)."""
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def step_of(unix_seconds: float) -> int:
    return int(unix_seconds // STEP_SECONDS)


def matching_step(
    secret: str, code: str, unix_seconds: float, after_step: int | None
) -> int | None:
    """The step this code belongs to, or None. A step at or before after_step (the last
    code already used) never counts, so one code cannot be used twice."""
    clean = code.strip().replace(" ", "")
    if len(clean) != DIGITS or not clean.isdigit():
        return None
    now = step_of(unix_seconds)
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if after_step is not None and step <= after_step:
            continue
        if hmac.compare_digest(code_at(secret, step), clean):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "AfriPeak Health") -> str:
    """The otpauth:// link an authenticator app reads (from a QR code, or tapped on a phone)."""
    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )
