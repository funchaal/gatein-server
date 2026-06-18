import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_company_user
from app.models import CompanyUser, Company, Appointment, AppointmentLayout

router = APIRouter()

@router.get("/sync")
def sync_dashboard(
    current_user: CompanyUser = Depends(get_current_company_user),
    db: Session = Depends(get_db)
):
    company_id = current_user.company_id
    company = db.query(Company).get(company_id)

    today = datetime.datetime.utcnow().date()
    
    count_today = 0
    schemas_list = []
    appt_list = []
    
    if company.type == 'terminal':
        count_today = (
            db.query(Appointment)
            .filter(
                Appointment.terminal_id == company_id,
                func.date(Appointment.schedule_start_time) == today,
                Appointment.status != "DELETED",
            )
            .count()
        )

        schemas = db.query(AppointmentLayout).filter_by(terminal_id=company_id).all()
        # Fallback for old layouts that might have 'operation_type' or not.
        schemas_list = [{"id": s.id, "title": s.title, "ref": s.ref} for s in schemas]

        recent_appointments = (
            db.query(Appointment)
            .filter(Appointment.terminal_id == company_id, Appointment.status != "DELETED")
            .order_by(Appointment.created_at.desc())
            .limit(10)
            .all()
        )
        appt_list = [
            {
                "ref": a.ref,
                "summary": a.summary,
                "plate": a.vehicle_plate,
                "status": a.status,
                "start": a.schedule_start_time.isoformat() if a.schedule_start_time else None,
            }
            for a in recent_appointments
        ]

    return {
        "success": True,
        "data": {
            "company_info": {
                "name": company.name,
                "address": {
                    "street": company.address_street,
                    "number": company.address_number,
                    "city": company.address_city,
                    "state": company.address_state,
                    "country": company.address_country,
                    "zip": company.address_zip,
                },
                "geofence": getattr(company, "geofence", {}),
                "api_key_prefix": company.api_key_prefix,
            },
            "user_info": {
                "username": current_user.username,
                "role": "Admin" if current_user.is_admin else "Operator",
                "permissions": current_user.permissions,
            },
            "dashboard_stats": {
                "appointments_today": count_today,
                "active_drivers": 0,
            },
            "resources": {
                "appointment_schemas_summary": schemas_list,
                "recent_appointments": appt_list,
                "trip_schemas": [],
            },
        },
    }