from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import logging

# Importação de Sockets
from app.api.sockets.connection import sio

# Importação de Roteadores Unificados
from app.api.health import router as health_router
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

# Configuração Global de Logging
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
if settings.is_development and settings.LOG_LEVEL == "INFO":
    log_level = logging.DEBUG

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)



from app.core.database import Base, engine
import app.models  # noqa: F401 - Register all ORM models



@asynccontextmanager
async def lifespan(application: FastAPI):
    """Gerencia o ciclo de vida do servidor: inicia e para o APScheduler."""
    logger.info(f"[AMBIENTE] Servidor iniciado em modo: {settings.ENVIRONMENT.upper()}")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[DATABASE] Sincronização de tabelas efetuada com sucesso.")
    except Exception as e:
        logger.error(f"[DATABASE] Erro ao sincronizar tabelas: {e}")
    start_scheduler()
    yield
    stop_scheduler()


# Inicialização do FastAPI com documentação padrão desativada
fastapi_app = FastAPI(
    title="GateIn API",
    version="1.0.0",
    docs_url=None if not settings.is_development else "/docs",
    redoc_url=None if not settings.is_development else "/redoc",
    openapi_url=None if not settings.is_development else "/openapi.json",
    lifespan=lifespan,
)

# Middleware CORS (Configurado via settings.ALLOWED_ORIGINS)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão de Rotas Unificadas
fastapi_app.include_router(health_router)
fastapi_app.include_router(mobile_router)
fastapi_app.include_router(web_router)
fastapi_app.include_router(public_router)
fastapi_app.include_router(admin_router)


# Inicialização do Socket.IO ASGI App
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    # Ele vai rodar o "app" que agora contém tanto o Socket.IO quanto o FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=settings.is_development)

