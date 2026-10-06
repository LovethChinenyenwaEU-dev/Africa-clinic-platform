"""Tiny in-process event bus.

Modules announce facts ("appointment.booked") and other modules react, so the
announcing module never has to know who is listening.

Rules:
- Payloads carry IDs and event types only, never names, notes or other PHI.
- Handlers run synchronously for now. Later, publish() can push to the Redis
  job queue without changing any caller.
"""
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Event:
    name: str
    tenant_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Handler = Callable[[Event], None]
_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(event_name: str, handler: Handler) -> None:
    _handlers[event_name].append(handler)


def publish(event: Event) -> None:
    for handler in list(_handlers[event.name]):
        handler(event)


def clear_handlers() -> None:
    """For tests only."""
    _handlers.clear()
