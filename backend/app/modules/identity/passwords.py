from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Turn a password into abstract password we can safely store."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check whether a typed password matches a stored abstract password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False