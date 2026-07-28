from sqlalchemy import text
from app.core.database import engine, Base

# Importe TODOS os seus modelos aqui
from app.models import (
    Company, Terminal, TruckingCompany,
    Appointment, Ticket, User, CompanyUser,
    Driver, RegisterRequest, Trip,
    AppointmentLayout, TicketLayout, TripLayout,
    Announcement, AppointmentLog, TripLog, AnnouncementLog
)

from config import settings

def hard_reset():
    if not settings.is_development:
        raise RuntimeError(f"ABORTED: sync_db.py hard_reset is strictly forbidden in {settings.ENVIRONMENT} mode!")

    print("⚠️ Iniciando o reset FORÇADO do banco de dados...")
    
    with engine.begin() as conn:
        print("1. Apagando schema public (CASCADE)...")
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        
        print("2. Recriando schema public vazio...")
        conn.execute(text("CREATE SCHEMA public;"))

        print("2.5 Recriando extensoes e funcoes...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
        conn.execute(text('''
            CREATE OR REPLACE FUNCTION f_unaccent(text)
            RETURNS text AS
            $func$
            SELECT public.unaccent('public.unaccent', $1)
            $func$ LANGUAGE sql IMMUTABLE;
        '''))

    print("3. Criando novas tabelas com a estrutura atualizada...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Banco de dados zerado e recriado com sucesso!")

if __name__ == "__main__":
    hard_reset()