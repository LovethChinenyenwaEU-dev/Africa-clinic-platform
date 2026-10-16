"""The Idempotency-Key header on writes (FR-O3).

A POST carrying `Idempotency-Key: <key>` runs once. Sending it again with the same
body gets the remembered answer and the header `Idempotent-Replayed: true`; nothing
runs twice. A POST without the header behaves exactly as before.

This is plain ASGI middleware so the request body can be read and still reach the
route, and the answer can be captured as it goes out.
"""
import json

from sqlmodel import Session
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.db import engine
from app.modules.idempotency.service import (
    InvalidKeyError,
    KeyReusedError,
    check_key,
    find_record,
    remember,
    request_hash,
    should_remember,
)
from app.modules.identity.service import get_staff_in_tenant
from app.modules.identity.tokens import InvalidTokenError, decode_access_token

HEADER = b"idempotency-key"


async def _send_json(send: Send, status: int, body: bytes, replayed: bool = False) -> None:
    headers = [(b"content-type", b"application/json")]
    if replayed:
        headers.append((b"idempotent-replayed", b"true"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _signed_in(headers: dict[bytes, bytes]):
    """(tenant_id, staff_id) of an active signed-in person, or None to let auth answer."""
    auth = headers.get(b"authorization", b"").decode()
    if not auth.lower().startswith("bearer "):
        return None
    try:
        claims = decode_access_token(auth[7:].strip())
    except InvalidTokenError:
        return None
    with Session(engine) as session:
        staff = get_staff_in_tenant(
            session, tenant_id=claims.tenant_id, staff_id=claims.staff_id
        )
        if staff is None or not staff.is_active:
            return None  # switched off: never replay anything to them
    return claims.tenant_id, claims.staff_id


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        raw_key = headers.get(HEADER)
        if raw_key is None:
            await self.app(scope, receive, send)
            return

        try:
            key = check_key(raw_key.decode(errors="replace"))
        except InvalidKeyError as error:
            await _send_json(send, 422, json.dumps({"detail": str(error)}).encode())
            return

        who = await run_in_threadpool(_signed_in, headers)
        if who is None:
            await self.app(scope, receive, send)  # the route's own guard answers 401
            return
        tenant_id, staff_id = who

        # Read the whole body once, then hand the same bytes to the route.
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        fingerprint = request_hash(
            "POST", scope["path"], scope.get("query_string", b"").decode(), body
        )

        def look_up():
            with Session(engine) as session:
                return find_record(
                    session,
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    key=key,
                    fingerprint=fingerprint,
                )

        try:
            record = await run_in_threadpool(look_up)
        except KeyReusedError as error:
            await _send_json(send, 422, json.dumps({"detail": str(error)}).encode())
            return
        if record is not None:
            await _send_json(
                send, record.status_code, record.response_body.encode(), replayed=True
            )
            return

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        status = 500
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, replay_body, capture)

        if should_remember(status):

            def store() -> None:
                with Session(engine) as session:
                    remember(
                        session,
                        tenant_id=tenant_id,
                        staff_id=staff_id,
                        key=key,
                        fingerprint=fingerprint,
                        status_code=status,
                        response_body=b"".join(chunks).decode(errors="replace"),
                    )

            await run_in_threadpool(store)
