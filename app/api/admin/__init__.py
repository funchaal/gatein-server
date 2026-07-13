from fastapi import APIRouter

from app.api.admin.system import router as system_router

router = APIRouter(prefix="/api/admin")

router.include_router(system_router, tags=["Admin"])
