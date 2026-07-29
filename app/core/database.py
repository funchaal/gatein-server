from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings
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

