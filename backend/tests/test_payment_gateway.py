"""The Paystack adapter on its own, with the network replaced by a fake."""
import hashlib
import hmac
import io
import json
import urllib.error

import pytest

from app.modules.billing import gateway as gateway_module
from app.modules.billing.gateway import (
    GatewayUnavailableError,
    NoGateway,
    PaystackGateway,
    payment_gateway,
)

SECRET = "sk_test_not_a_real_key"


@pytest.fixture
def paystack():
    return PaystackGateway(SECRET, "https://api.paystack.test")


@pytest.fixture
def network(monkeypatch):
    """Records each request and answers with what the test put in `answers`."""
    calls = {"requests": [], "answers": []}

    def fake_urlopen(request, timeout):
        calls["requests"].append(request)
        answer = calls["answers"].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())

    monkeypatch.setattr(gateway_module.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_only_paystacks_own_signature_is_accepted(paystack):
    body = b'{"event":"charge.success"}'
    good = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()

    assert paystack.signature_ok(body, good)
    assert not paystack.signature_ok(body + b" ", good)  # the body was changed
    assert not paystack.signature_ok(body, None)
    assert not paystack.signature_ok(body, "")


def test_initialize_sends_kobo_in_naira_with_the_secret_key(paystack, network):
    network["answers"].append(
        {"status": True, "data": {"authorization_url": "https://checkout.paystack.com/x"}}
    )

    url = paystack.initialize(
        reference="LFY-1", amount_kobo=500_000, email="a@b.co", metadata={"invoice_number": "1"}
    )

    sent = network["requests"][0]
    assert url == "https://checkout.paystack.com/x"
    assert sent.full_url == "https://api.paystack.test/transaction/initialize"
    assert sent.get_method() == "POST"
    assert sent.get_header("Authorization") == f"Bearer {SECRET}"
    assert json.loads(sent.data) == {
        "reference": "LFY-1",
        "amount": 500_000,
        "currency": "NGN",
        "email": "a@b.co",
        "metadata": {"invoice_number": "1"},
    }


def test_verify_reads_status_amount_and_currency(paystack, network):
    data = {"status": "success", "amount": 500_000, "currency": "NGN", "id": 9}
    network["answers"].append({"status": True, "data": data})

    result = paystack.verify(reference="LFY-1")

    assert network["requests"][0].full_url == "https://api.paystack.test/transaction/verify/LFY-1"
    assert (result.status, result.amount_kobo, result.currency, result.transaction_id) == (
        "success",
        500_000,
        "NGN",
        "9",
    )


def test_a_network_failure_or_refusal_never_shows_the_key(paystack, network):
    network["answers"].extend(
        [urllib.error.URLError("no route"), {"status": False, "message": "Invalid key"}]
    )

    for _ in range(2):
        with pytest.raises(GatewayUnavailableError) as caught:
            paystack.verify(reference="LFY-1")
        assert SECRET not in str(caught.value)


def test_paystack_needs_a_key_and_none_is_the_safe_default(monkeypatch):
    with pytest.raises(GatewayUnavailableError):
        PaystackGateway("", "https://api.paystack.test")

    monkeypatch.setattr(gateway_module.settings, "payment_gateway", "none")
    off = payment_gateway()
    assert isinstance(off, NoGateway)
    assert not off.signature_ok(b"{}", "anything")
    with pytest.raises(GatewayUnavailableError):
        off.verify(reference="LFY-1")
