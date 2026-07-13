from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.models import Trip

def migrate_and_update():
    # 1. Alter Table to add columns if they don't exist
    alter_queries = [
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_street VARCHAR(150);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_number VARCHAR(20);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_city VARCHAR(100);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_state VARCHAR(50);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_country VARCHAR(50);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_zip VARCHAR(20);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_lat FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS origin_lng FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_street VARCHAR(150);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_number VARCHAR(20);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_city VARCHAR(100);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_state VARCHAR(50);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_country VARCHAR(50);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_zip VARCHAR(20);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_lat FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS destiny_lng FLOAT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS from_location VARCHAR(100);",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS to_location VARCHAR(100);",
        "ALTER TABLE appointments DROP COLUMN IF EXISTS operation_type;"
    ]
    
    print("Running database migration...")
    with engine.begin() as conn:
        for query in alter_queries:
            conn.execute(text(query))
    print("Migration successful!")

    # 2. Update existing trips
    print("Updating existing trips...")
    db = SessionLocal()
    try:
        trips = db.query(Trip).all()
        for trip in trips:
            # Set default mock values for origin
            trip.origin_street = "Av. Eng. Fábio Roberto Barnabé"
            trip.origin_number = "1500"
            trip.origin_city = "Santos"
            trip.origin_state = "SP"
            trip.origin_country = "Brasil"
            trip.origin_zip = "11095-890"
            trip.origin_lat = -23.91160956216094
            trip.origin_lng = -46.31284453534403

            # Set default mock values for destiny
            trip.destiny_street = "Av. Eduardo Guinle"
            trip.destiny_number = "S/N"
            trip.destiny_city = "Santos"
            trip.destiny_state = "SP"
            trip.destiny_country = "Brasil"
            trip.destiny_zip = "11095-000"
            trip.destiny_lat = -23.924156643454374
            trip.destiny_lng = -46.34930933223951

            # Top from/to routes
            trip.from_location = "Campinas - SP"
            trip.to_location = "Macaé - RJ"
        db.commit()
        print(f"Updated {len(trips)} existing trips!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate_and_update()
