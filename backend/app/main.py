from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import app.model_registry  # noqa: F401
from app.api import api_router
from app.core.config import settings
from app.core.db import engine
from app.core.device import DeviceMiddleware
from app.modules.idempotency.middleware import IdempotencyMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """On hosts without background workers (Render's free plan), the reminder worker runs
    inside the API when RUN_WORKER_IN_API is true (Week 12)."""
    stop = None
    if settings.run_worker_in_api:
        from app.worker import start_in_background

        stop = start_in_background()
    yield
    if stop is not None:
        stop.set()


app = FastAPI(title="Clinic Platform API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
# A write sent twice with the same Idempotency-Key happens once (FR-O3).
app.add_middleware(IdempotencyMiddleware)
# Which device each request came from, for the audit diary (FR-A2).
app.add_middleware(DeviceMiddleware)


app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    """Readiness: database and Redis are reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        redis.Redis.from_url(settings.redis_url).ping()
    except (SQLAlchemyError, redis.RedisError, OSError):
        raise HTTPException(status_code=503, detail="dependency unavailable") from None
    return {"status": "ready"}
