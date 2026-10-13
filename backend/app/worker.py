"""Background worker: sends due reminders every few seconds.

Run with: python -m app.worker

The reminder table is the queue. It is durable, survives restarts, and several
workers can share it safely (see notifications/sender.py). Redis holds a
heartbeat, the time of the last finished run, so anyone can check the worker
is alive.

Logs carry counts and error types only, never phone numbers or message text.
"""
import logging
import signal
import threading
import uuid
from datetime import UTC, datetime

import redis
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

import app.model_registry  # noqa: F401  (registers all module tables)
from app.core.config import settings
from app.core.db import engine
from app.modules.notifications.adapters import MessageAdapter, make_adapter
from app.modules.notifications.sender import SendRun, send_due_reminders

HEARTBEAT_KEY = "worker:reminders:last_run"

logger = logging.getLogger("app.worker")


def run_once(
    session: Session,
    redis_client: redis.Redis,
    *,
    adapter: MessageAdapter,
    now: datetime | None = None,
    tenant_id: uuid.UUID | None = None,
) -> SendRun:
    """One tick: send what is due, then record the heartbeat."""
    current = now or datetime.now(UTC)
    result = send_due_reminders(session, adapter=adapter, now=current, tenant_id=tenant_id)
    redis_client.set(HEARTBEAT_KEY, current.isoformat())
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    adapter = make_adapter(settings.sms_provider)
    redis_client = redis.Redis.from_url(settings.redis_url)

    stopping = threading.Event()
    # Docker sends SIGTERM on `docker compose stop`; finish the current tick, then exit.
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())

    logger.info(
        "reminder worker started: provider=%s every %ss",
        settings.sms_provider,
        settings.reminder_interval_seconds,
    )
    while not stopping.is_set():
        try:
            with Session(engine) as session:
                result = run_once(session, redis_client, adapter=adapter)
            if result.sent or result.retrying or result.failed or result.cancelled:
                logger.info(
                    "reminders: sent=%d retrying=%d failed=%d cancelled=%d",
                    result.sent,
                    result.retrying,
                    result.failed,
                    result.cancelled,
                )
        except (SQLAlchemyError, redis.RedisError, OSError) as error:
            # Only the error type: database errors can echo query values.
            logger.warning(
                "reminder tick failed (%s); trying again next tick", type(error).__name__
            )
        stopping.wait(settings.reminder_interval_seconds)
    logger.info("reminder worker stopped")


if __name__ == "__main__":
    main()
