import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.core.dependencies import get_current_company_user
from app.models import CompanyUser, Company, Appointment, AppointmentLayout

router = APIRouter()

# --- RESPONSE SCHEMAS ---

class SyncCompanyAddressSchema(BaseModel):
    """Schema representing company address fields in dashboard synchronizations."""
    street: Optional[str] = None
    number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None

class SyncCompanyInfoSchema(BaseModel):
    """Schema representing company summary data for landing configurations."""
    name: str
    address: SyncCompanyAddressSchema
    geofence: Optional[Dict[str, Any]] = None
    api_key_prefix: Optional[str] = None

class SyncUserInfoSchema(BaseModel):
    """Schema representing active operator user details."""
    username: str
    role: str
    permissions: Dict[str, Any]

class SyncDashboardStatsSchema(BaseModel):
    """Schema detailing core operational KPIs for today's tasks."""
    appointments_today: int
    active_drivers: int

class SyncAppointmentSchemaSummary(BaseModel):
    """Schema mapping registered layout templates for appointment forms."""
    id: int
    title: str
    ref: str

class SyncRecentAppointment(BaseModel):
    """Schema detailing individual recent appointment records."""
    ref: str
    summary: str
    plate: Optional[str] = None
    status: str
    start: Optional[str] = None

class SyncResourcesSchema(BaseModel):
    """Container holding layout configurations and recent activity lists."""
    appointment_schemas_summary: List[SyncAppointmentSchemaSummary]
    recent_appointments: List[SyncRecentAppointment]
    trip_schemas: List[Any] = []

class SyncDashboardData(BaseModel):
    """Dashboard synchronization root payload schema."""
    company_info: SyncCompanyInfoSchema
    user_info: SyncUserInfoSchema
    dashboard_stats: SyncDashboardStatsSchema
    resources: SyncResourcesSchema

class SyncDashboardResponse(BaseModel):
    """Response containing unified dashboard sync data."""
    success: bool = True
    data: SyncDashboardData


# --- ROTAS ---

@router.get(
    "/sync", 
    response_model=SyncDashboardResponse,
    summary="Sync Dashboard Data",
    description="Fetches company metadata, active operator profiles, basic landing stats, and recent appointments lists."
)
def sync_dashboard(
    current_user: CompanyUser = Depends(get_current_company_user),
    db: Session = Depends(get_db)
):
    """
    Syncs operator dashboard parameters on landing or refresh.
    """
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