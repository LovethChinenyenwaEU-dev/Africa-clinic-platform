"""The one door to online payment gateways (Week 10 Step 5, FR-B2, FR-B4).

Billing asks a PaymentGateway for a payment link and, later, whether a payment went
through. Swapping Paystack for Flutterwave means one new class here; nothing else changes.

Paystack:
- initialize: POST /transaction/initialize gives the link the patient pays on.
- verify: GET /transaction/verify/<reference> says what really happened. A webhook is
  only a hint until verify agrees.
- webhooks are signed: x-paystack-signature is the HMAC-SHA512 of the raw body made
  with the secret key. Anything unsigned or wrongly signed is ignored.

The secret key lives only in the server's settings (PAYSTACK_SECRET_KEY), never in code,
logs, screens or answers.
"""
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings

TIMEOUT_SECONDS = 15


class GatewayUnavailableError(Exception):
    """No gateway is set up on this server, or it could not be reached."""


@dataclass(frozen=True)
class GatewayResult:
    """What the gateway says happened to one payment."""

    status: str  # success, failed, abandoned, pending (anything else counts as pending)
    amount_kobo: int
    currency: str
    transaction_id: str | None = None


class PaymentGateway(Protocol):
    name: str

    def initialize(
        self, *, reference: str, amount_kobo: int, email: str, metadata: dict[str, str]
    ) -> str: ...

    def verify(self, *, reference: str) -> GatewayResult: ...

    def signature_ok(self, body: bytes, signature: str | None) -> bool: ...


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


class PaystackGateway:
    name = "paystack"

    def __init__(self, secret_key: str, base_url: str, callback_url: str = "") -> None:
        if not secret_key:
            raise GatewayUnavailableError("Paystack is not set up (no secret key).")
        self._secret = secret_key
        self._base = base_url.rstrip("/")
        self._callback = callback_url

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self._base}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._secret}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                answer = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            # Never echo the request: it carries the secret key in a header.
            raise GatewayUnavailableError("Paystack could not be reached.") from error
        if not answer.get("status"):
            raise GatewayUnavailableError("Paystack refused the request.")
        return answer.get("data") or {}

    def initialize(
        self, *, reference: str, amount_kobo: int, email: str, metadata: dict[str, str]
    ) -> str:
        payload: dict = {
            "reference": reference,
            "amount": amount_kobo,  # Paystack counts in kobo too
            "currency": "NGN",
            "email": email,
            "metadata": metadata,
        }
        if self._callback:
            payload["callback_url"] = self._callback
        data = self._call("POST", "/transaction/initialize", payload)
        url = data.get("authorization_url")
        if not url:
            raise GatewayUnavailableError("Paystack gave no payment link.")
        return str(url)

    def verify(self, *, reference: str) -> GatewayResult:
        data = self._call("GET", f"/transaction/verify/{reference}")
        return GatewayResult(
            status=str(data.get("status", "pending")),
            amount_kobo=int(data.get("amount", 0)),
            currency=str(data.get("currency", "")),
            transaction_id=str(data["id"]) if data.get("id") is not None else None,
        )

    def signature_ok(self, body: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        return hmac.compare_digest(_sign(self._secret, body), signature)


@dataclass
class FakeGateway:
    """For tests: nothing leaves the machine. Tests say what verify should answer."""

    secret: str = "fake-gateway-secret"
    name: str = "fake"
    initialized: list[dict] = field(default_factory=list)
    outcomes: dict[str, GatewayResult] = field(default_factory=dict)
    unreachable: bool = False

    def initialize(
        self, *, reference: str, amount_kobo: int, email: str, metadata: dict[str, str]
    ) -> str:
        if self.unreachable:
            raise GatewayUnavailableError("The fake gateway is down.")
        self.initialized.append(
            {"reference": reference, "amount_kobo": amount_kobo, "email": email, **metadata}
        )
        return f"https://pay.invalid/{reference}"

    def verify(self, *, reference: str) -> GatewayResult:
        if self.unreachable:
            raise GatewayUnavailableError("The fake gateway is down.")
        return self.outcomes.get(reference, GatewayResult("pending", 0, "NGN"))

    def signature_ok(self, body: bytes, signature: str | None) -> bool:
        return bool(signature) and hmac.compare_digest(_sign(self.secret, body), signature or "")

    def sign(self, body: bytes) -> str:
        """What a real gateway would put in the signature header."""
        return _sign(self.secret, body)


class NoGateway:
    """Online payment switched off: cash and transfer only."""

    name = "none"

    def initialize(
        self, *, reference: str, amount_kobo: int, email: str, metadata: dict[str, str]
    ) -> str:
        raise GatewayUnavailableError("Online payment is not set up on this server.")

    def verify(self, *, reference: str) -> GatewayResult:
        raise GatewayUnavailableError("Online payment is not set up on this server.")

    def signature_ok(self, body: bytes, signature: str | None) -> bool:
        return False


def payment_gateway() -> PaymentGateway:
    """The gateway this server is set up for (PAYMENT_GATEWAY). Tests swap this function."""
    if settings.payment_gateway == "paystack":
        return PaystackGateway(
            settings.paystack_secret_key,
            settings.paystack_base_url,
            settings.paystack_callback_url,
        )
    return NoGateway()
