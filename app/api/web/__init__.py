from fastapi import APIRouter

from app.api.web.auth import router as web_auth_router
from app.api.web.sync import router as web_sync_router
from app.api.web.users import router as web_users_router
from app.api.web.services import router as web_services_router
from app.api.web.config import router as web_config_router
from app.api.web.appointments_layout import router as appointments_layout_router
from app.api.web.tickets_layout import router as tickets_layout_router
from app.api.web.trips_layout import router as trips_layout_router
from app.api.web.apiKey import router as api_keys_router
from app.api.web.announcements import router as web_announcements_router

router = APIRouter(prefix="/api/web")

router.include_router(web_auth_router, prefix="/auth", tags=["Web Auth"])
router.include_router(web_sync_router, tags=["Web Sync"])
router.include_router(web_users_router, tags=["Web Users"])
router.include_router(web_services_router, tags=["Web Services"])
router.include_router(web_config_router, prefix="/config", tags=["Web Config"])
router.include_router(appointments_layout_router, prefix="/config", tags=["Web Appointment Layouts"])
router.include_router(tickets_layout_router, prefix="/config", tags=["Web Ticket Layouts"])
router.include_router(trips_layout_router, prefix="/config", tags=["Web Trip Layouts"])
router.include_router(api_keys_router, prefix="/api-key", tags=["API Keys"])
router.include_router(web_announcements_router, tags=["Web Announcements"])
