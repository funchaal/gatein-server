# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.mobile.auth import router as mobile_auth_router
from app.api.mobile.password_recovery import router as mobile_password_router
from app.api.mobile.sync import router as mobile_sync_router
from app.api.mobile.services import router as mobile_services_router
from app.api.web.auth import router as web_auth_router
from app.api.web.sync import router as web_sync_router
from app.api.web.users import router as web_users_router
from app.api.web.services import router as web_services_router
from app.api.web.config import router as web_config_router
from app.api.web.appointments_layout import router as appointments_layout_router
from app.api.web.tickets_layout import router as tickets_layout_router
from app.api.web.trips_layout import router as trips_layout_router
from app.api.web.apiKey import router as api_keys_router
from app.api.mobile.checkin import router as mobile_checkin_router
from app.api.integration.appointments import router as integration_router
from app.api.integration.auth import router as integration_auth_router
from app.api.system.system import router as system_router
from app.api.mobile.companies import router as mobile_companies_router


# Importa a aplicação ASGI do Socket.IO e a instância do servidor
from app.sockets import sio
import socketio

# 1. Mude o nome da variável do FastAPI (ex: fastapi_app)
fastapi_app = FastAPI(title="GateIn API", version="1.0.0")

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas REST
fastapi_app.include_router(mobile_auth_router, prefix="/api/v1/mobile/auth",  tags=["Mobile Auth"])
fastapi_app.include_router(mobile_password_router, prefix="/api/v1/mobile/password", tags=["Mobile Password"])
fastapi_app.include_router(mobile_sync_router, prefix="/api/v1/mobile",  tags=["Mobile Sync"])
fastapi_app.include_router(mobile_services_router, prefix="/api/v1/mobile", tags=["Mobile Services"])
fastapi_app.include_router(mobile_companies_router, prefix="/api/v1/mobile", tags=["Mobile Companies"])
fastapi_app.include_router(mobile_checkin_router, prefix="/api/v1/mobile/checkin", tags=["Mobile Checkin"])

fastapi_app.include_router(web_auth_router,    prefix="/api/v1/web/auth",     tags=["Web Auth"])
fastapi_app.include_router(web_sync_router,    prefix="/api/v1/web",          tags=["Web Sync"])
fastapi_app.include_router(web_users_router,   prefix="/api/v1/web",          tags=["Web Users"])
fastapi_app.include_router(web_services_router,prefix="/api/v1/web",          tags=["Web Services"])
fastapi_app.include_router(web_config_router,  prefix="/api/v1/web/config",   tags=["Web Config"])
fastapi_app.include_router(appointments_layout_router, prefix="/api/v1/web/config", tags=["Web Appointment Layouts"])
fastapi_app.include_router(tickets_layout_router, prefix="/api/v1/web/config", tags=["Web Ticket Layouts"])
fastapi_app.include_router(trips_layout_router, prefix="/api/v1/web/config", tags=["Web Trip Layouts"])
fastapi_app.include_router(api_keys_router,    prefix="/api/v1/web/api-key", tags=["API Keys"])

fastapi_app.include_router(integration_router, prefix="/api/v1/integration",  tags=["Integration"])
fastapi_app.include_router(integration_auth_router, prefix="/api/v1/integration",  tags=["Integration Auth"])
fastapi_app.include_router(system_router,      prefix="/api/v1/system",       tags=["System"])

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    # Ele vai rodar o "app" que agora contém tanto o Socket.IO quanto o FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)