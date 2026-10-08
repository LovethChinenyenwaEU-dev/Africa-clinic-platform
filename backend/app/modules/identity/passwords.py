from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher()


class WeakPasswordError(ValueError):
    """Raised when a password does not meet our rules."""


def check_password_rules(password: str) -> None:
    """Raise WeakPasswordError if the password is too short or too long."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
        )


def hash_password(password: str) -> str:
    """Turn a password into abstract password we can safely store."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check whether a typed password matches a stored abstract password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False