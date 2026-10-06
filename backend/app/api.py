from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Each module registers its router here when it has one, for example:
#
#   from app.modules.tenancy.router import router as tenancy_router
#   api_router.include_router(tenancy_router, prefix="/tenancy", tags=["tenancy"])
