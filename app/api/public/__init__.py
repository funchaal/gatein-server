from fastapi import APIRouter

from app.api.public.appointments import router as public_api_router
from app.api.public.auth import router as public_api_auth_router
from app.api.public.trips import router as public_api_trips_router
from app.api.public.services import router as public_api_services_router

router = APIRouter(prefix="/api/v1")

router.include_router(public_api_router, tags=["Appointments"])
router.include_router(public_api_auth_router, tags=["Authentication"])
router.include_router(public_api_trips_router, tags=["Trips"])
router.include_router(public_api_services_router, tags=["Services"])

