from fastapi import APIRouter

from app.modules.identity.router import router as identity_router

api_router = APIRouter(prefix="/api/v1")

# Each module registers its router here when it has one.
api_router.include_router(identity_router)