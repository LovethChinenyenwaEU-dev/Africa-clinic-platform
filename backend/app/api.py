from fastapi import APIRouter

from app.modules.identity.router import router as identity_router
from app.modules.identity.staff_router import router as staff_router
from app.modules.tenancy.router import router as tenancy_router

api_router = APIRouter(prefix="/api/v1")

# Each module registers its router here when it has one.
api_router.include_router(identity_router)
api_router.include_router(staff_router)
api_router.include_router(tenancy_router)