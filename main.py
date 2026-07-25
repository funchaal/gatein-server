from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import logging

# Importação de Sockets
from app.api.sockets.connection import sio

# Importação de Roteadores Unificados
from app.api.mobile import router as mobile_router
from app.api.web import router as web_router
from app.api.public import router as public_router
from app.api.admin import router as admin_router

# Scheduler de notificações
from app.core.scheduler import start_scheduler, stop_scheduler

# Firebase — inicializa o SDK na importação
import app.core.firebase  # noqa: F401

# Tenant Isolation — registra o event listener ORM (ativo apenas em PROD=False)
import app.core.tenant  # noqa: F401

# Filtro Automático de Registros Ativos — registra o event listener ORM (is_active = True)
import app.core.active  # noqa: F401

from config import settings

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(application: FastAPI):
    """Gerencia o ciclo de vida do servidor: inicia e para o APScheduler."""
    env_label = "PRODUCAO" if settings.IS_PROD else "STAGING (homologacao)"
    logger.info(f"[AMBIENTE] Servidor iniciado em modo: {env_label}")
    start_scheduler()
    yield
    stop_scheduler()


# Inicialização do FastAPI com documentação padrão desativada
fastapi_app = FastAPI(
    title="GateIn API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# Middleware CORS (Configurado apenas uma vez)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão de Rotas Unificadas
fastapi_app.include_router(mobile_router)
fastapi_app.include_router(web_router)
fastapi_app.include_router(public_router)
fastapi_app.include_router(admin_router)


# Inicialização do Socket.IO ASGI App
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    # Ele vai rodar o "app" que agora contém tanto o Socket.IO quanto o FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)

