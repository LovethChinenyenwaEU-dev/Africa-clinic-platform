"""The one door to SMS/WhatsApp providers.

The rest of the app talks to MessageAdapter only. Swapping Termii, Twilio or
Africa's Talking means writing one new class here, nothing else changes.

Rules:
- Adapters never log the phone number or the message text.
- A failure raises ProviderError. retryable says whether trying again can help
  (provider down, timeout) or not (bad number, rejected content).
"""
import uuid
from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    """The provider could not send the message."""

    def __init__(self, reason: str, *, retryable: bool) -> None:
        super().__init__(reason)
        self.retryable = retryable


@dataclass(frozen=True)
class OutgoingMessage:
    to: str  # standard form, like +2348031234567
    body: str
    channel: str = "sms"  # sms or whatsapp


@dataclass(frozen=True)
class SendReceipt:
    provider_message_id: str


class MessageAdapter(Protocol):
    def send(self, message: OutgoingMessage) -> SendReceipt: ...


@dataclass
class FakeAdapter:
    """Sends nothing. For tests and local development.

    fail_times makes the first N sends fail, so retry logic can be tested.
    """

    fail_times: int = 0
    retryable: bool = True
    sent: list[OutgoingMessage] = field(default_factory=list)

    def send(self, message: OutgoingMessage) -> SendReceipt:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ProviderError("fake provider failure", retryable=self.retryable)
        self.sent.append(message)
        return SendReceipt(provider_message_id=f"fake-{uuid.uuid4()}")


class NullAdapter:
    """Pretends every send worked and keeps nothing. For running the worker before
    a real provider is set up, so no patient is ever messaged by accident."""

    def send(self, message: OutgoingMessage) -> SendReceipt:
        return SendReceipt(provider_message_id=f"none-{uuid.uuid4()}")


class UnknownProviderError(ValueError):
    """The configured SMS provider name is not one we have an adapter for."""


def make_adapter(provider: str) -> MessageAdapter:
    """Pick the adapter named in settings. A new provider is one more line here."""
    if provider == "none":
        return NullAdapter()
    raise UnknownProviderError(f"No SMS adapter called {provider!r}.")
