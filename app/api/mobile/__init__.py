from fastapi import APIRouter

from app.api.mobile.auth import router as mobile_auth_router
from app.api.mobile.password_recovery import router as mobile_password_router
from app.api.mobile.activities import router as mobile_activities_router
from app.api.mobile.services import router as mobile_services_router
from app.api.mobile.companies import router as mobile_companies_router
from app.api.mobile.checkin import router as mobile_checkin_router
from app.api.mobile.announcements import router as mobile_announcements_router

router = APIRouter(prefix="/api/mobile")

router.include_router(mobile_auth_router, prefix="/auth", tags=["Mobile Auth"])
router.include_router(mobile_password_router, prefix="/password", tags=["Mobile Password"])
router.include_router(mobile_activities_router, tags=["Mobile Activities"])
router.include_router(mobile_services_router, tags=["Mobile Services"])
router.include_router(mobile_companies_router, tags=["Mobile Companies"])
router.include_router(mobile_checkin_router, prefix="/checkin", tags=["Websocket & Checkin"])
router.include_router(mobile_announcements_router, tags=["Mobile Announcements"])
