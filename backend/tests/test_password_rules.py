import pytest

from app.modules.identity.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    WeakPasswordError,
    check_password_rules,
)


def test_short_password_is_rejected():
    with pytest.raises(WeakPasswordError):
        check_password_rules("short")


def test_password_at_minimum_length_is_accepted():
    check_password_rules("a" * MIN_PASSWORD_LENGTH)


def test_password_one_over_the_maximum_is_rejected():
    with pytest.raises(WeakPasswordError):
        check_password_rules("a" * (MAX_PASSWORD_LENGTH + 1))