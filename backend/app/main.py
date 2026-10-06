import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_router
from app.core.config import settings
from app.core.db import engine

app = FastAPI(title="Clinic Platform API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
