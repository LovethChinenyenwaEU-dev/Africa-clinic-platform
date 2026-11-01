"""Week 12: secrets kept in the database are encrypted with a key that is not."""
import pytest

from app.core import secret_box
from app.core.config import settings


@pytest.fixture
def keys(monkeypatch):
    def use(value, environment="test"):
        monkeypatch.setattr(settings, "data_encryption_keys", value)
        monkeypatch.setattr(settings, "environment", environment)

    return use


def test_a_sealed_value_opens_to_the_same_value(keys):
    keys("a-long-random-key-for-testing-only-1")

    sealed = secret_box.seal("JBSWY3DPEHPK3PXP")

    assert sealed.startswith("enc:v1:")
    assert "JBSWY3DPEHPK3PXP" not in sealed
    assert secret_box.open_value(sealed) == "JBSWY3DPEHPK3PXP"
    assert secret_box.seal("JBSWY3DPEHPK3PXP") != sealed  # a fresh random IV each time


def test_a_plain_value_from_before_is_read_as_it_is(keys):
    keys("a-long-random-key-for-testing-only-1")

    assert secret_box.open_value("JBSWY3DPEHPK3PXP") == "JBSWY3DPEHPK3PXP"


def test_the_wrong_key_cannot_open_it(keys):
    keys("a-long-random-key-for-testing-only-1")
    sealed = secret_box.seal("JBSWY3DPEHPK3PXP")

    keys("a-different-key-entirely-for-tests-2")

    with pytest.raises(secret_box.SecretUnreadableError):
        secret_box.open_value(sealed)


def test_a_changed_value_is_refused(keys):
    keys("a-long-random-key-for-testing-only-1")
    sealed = secret_box.seal("JBSWY3DPEHPK3PXP")
    tampered = sealed[:-6] + ("A" if sealed[-6] != "A" else "B") + sealed[-5:]

    with pytest.raises(secret_box.SecretUnreadableError):
        secret_box.open_value(tampered)


def test_changing_the_key_keeps_old_values_readable_and_reseals_them(keys):
    keys("old-key-for-testing-only-0123456789")
    old = secret_box.seal("JBSWY3DPEHPK3PXP")

    keys("new-key-for-testing-only-9876543210,old-key-for-testing-only-0123456789")
    assert secret_box.open_value(old) == "JBSWY3DPEHPK3PXP"
    resealed = secret_box.reseal(old)

    keys("new-key-for-testing-only-9876543210")  # the old key removed
    assert secret_box.open_value(resealed) == "JBSWY3DPEHPK3PXP"


def test_production_without_a_key_refuses_to_start_sealing(keys):
    keys("", environment="production")

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEYS"):
        secret_box.seal("JBSWY3DPEHPK3PXP")


def test_development_without_a_key_uses_the_development_key(keys):
    keys("", environment="development")

    assert secret_box.open_value(secret_box.seal("x")) == "x"
