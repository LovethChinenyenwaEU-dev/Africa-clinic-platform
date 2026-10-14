from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.consent.router import router as consent_router
from app.modules.identity.router import router as identity_router
from app.modules.identity.staff_router import router as staff_router
from app.modules.patients.router import router as patients_router
from app.modules.records.router import router as records_router
from app.modules.scheduling.router import router as scheduling_router
from app.modules.tenancy.router import router as tenancy_router

api_router = APIRouter(prefix="/api/v1")

# Each module registers its router here when it has one.
api_router.include_router(audit_router)
api_router.include_router(consent_router)
api_router.include_router(identity_router)
api_router.include_router(staff_router)
api_router.include_router(patients_router)
api_router.include_router(records_router)
api_router.include_router(scheduling_router)
api_router.include_router(tenancy_router)