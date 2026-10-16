"""Which device a request came from, so the audit diary can say (FR-A2).

The browser sends `X-Device-Id`: a random UUID it made once and keeps. It is not a
fingerprint and says nothing about the hardware. A missing or malformed value is
simply treated as "unknown device".

The value lives in a context variable for the length of one request, so the diary
can read it without every service passing it along, and it can never leak into
another request.
"""
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

HEADER = b"x-device-id"

_current: ContextVar[uuid.UUID | None] = ContextVar("current_device_id", default=None)


def parse_device_id(raw: bytes | str | None) -> uuid.UUID | None:
    """A device ID, or None if it is missing or not a proper UUID."""
    if raw is None:
        return None
    text = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
    try:
        return uuid.UUID(text.strip())
    except ValueError:
        return None


def current_device_id() -> uuid.UUID | None:
    """The device of the request being handled now, or None (unknown, or no request)."""
    return _current.get()


class DeviceMiddleware:
    """Reads X-Device-Id once per request and makes it available to the diary."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _current.set(parse_device_id(dict(scope["headers"]).get(HEADER)))
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)
