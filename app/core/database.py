from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# --- SQLAlchemy (Banco Atual) ---
# engine = create_engine(settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# Dependency para injetar sessão nas rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Supabase ---
supabase: Client | None = None
# Trava de Segurança: Supabase é desativado em ambiente de desenvolvimento local
if settings.USE_SUPABASE and not settings.is_development:
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info(f"[Supabase] Conexão iniciada com sucesso ({settings.ENVIRONMENT.upper()})")
    else:
        logger.warning(f"[Supabase] USE_SUPABASE=True, mas SUPABASE_URL ou SUPABASE_KEY não estão configurados em {settings.ENVIRONMENT.upper()}.")
else:
    if settings.is_development:
        logger.info("[Supabase] Ignorado em ambiente de desenvolvimento (uso exclusivo do Postgres local).")