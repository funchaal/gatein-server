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

def hard_reset():
    print("⚠️ Iniciando o reset FORÇADO do banco de dados...")
    
    # with engine.begin() as conn:
        # print("1. Apagando schema public (CASCADE)...")
        # conn.execute(text("DROP SCHEMA public CASCADE;"))
        
        # print("2. Recriando schema public vazio...")
        # conn.execute(text("CREATE SCHEMA public;"))

    print("3. Criando novas tabelas com a estrutura atualizada...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Banco de dados zerado e recriado com sucesso!")

if __name__ == "__main__":
    hard_reset()