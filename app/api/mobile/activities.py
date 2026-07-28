import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.sqids import encode_id, decode_id
from app.models import (
    User, Appointment, Trip, Terminal, TruckingCompany, 
    AppointmentLayout, TicketLayout, TripLayout, AppointmentLog, TripLog,
    AppointmentEvent, TripEvent, SafetyIntegration
)

router = APIRouter()

# --- SCHEMAS (Pydantic Request/Response) ---

class TicketResponseSchema(BaseModel):
    """Schema representing validated ticket details."""
    id: str
    layout_ref: Optional[str] = None
    content: Dict[str, Any]
    created_at: str

class AppointmentResponseSchema(BaseModel):
    """Schema representing detailed appointment information."""
    id: str
    type: str = "appointment"
    ref: Optional[str] = None
    terminal_id: str
    layout_ref: Optional[str] = None
    status: str
    summary: Optional[str] = None
    license_plate: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    start_tolerance: int
    end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
    is_safety_integration_pending: Optional[bool] = None
    tickets: List[TicketResponseSchema]

class AddressSchema(BaseModel):
    """Schema representing general geographic address metrics."""
    street: Optional[str] = None
    number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class TripResponseSchema(BaseModel):
    """Schema representing detailed trip information."""
    id: str
    type: str = "trip"
    ref: Optional[str] = None
    trucking_company_id: str
    layout_ref: Optional[str] = None
    status: str
    summary: Optional[str] = None
    license_plate: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    start_tolerance: int
    end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
    from_: Optional[str] = Field(None, serialization_alias="from", validation_alias="from")
    to: Optional[str] = None
    origin: AddressSchema
    destiny: AddressSchema

class TerminalResponseSchema(BaseModel):
    """Schema representing terminal company details."""
    id: str
    name: str
    branch_name: Optional[str] = None
    logo_url: Optional[str] = None
    use_remote_checkin: bool
    address: AddressSchema
    geofence: Optional[Dict[str, Any]] = None
    safety_integration_active: bool = False
    safety_integration_video_url: Optional[str] = None
    safety_integration_form_url: Optional[str] = None
    safety_integration_blocks_checkin: bool = False

class TruckingCompanyResponseSchema(BaseModel):
    """Schema representing trucking company details."""
    id: Optional[str] = None
    name: str
    branch_name: Optional[str] = None
    logo_url: Optional[str] = None
    address: AddressSchema

class LayoutInfoSchema(BaseModel):
    """Schema representing customized layout details."""
    title: Optional[str] = None
    layout: Dict[str, Any]

class LayoutsDataSchema(BaseModel):
    """Schema grouping layout options by activity category."""
    appointment: Dict[str, LayoutInfoSchema]
    ticket: Dict[str, LayoutInfoSchema]
    trip: Dict[str, LayoutInfoSchema]

class ActivitiesResponseMeta(BaseModel):
    """Metadata detailing pagination constraints and availability."""
    has_more: bool
    limit: int
    offset: int

class ActivitiesResponseData(BaseModel):
    """Wrapper holding grouped entities returned by query."""
    appointments: List[AppointmentResponseSchema]
    trips: List[TripResponseSchema]
    terminals: Dict[str, TerminalResponseSchema]
    trucking_companies: Dict[str, TruckingCompanyResponseSchema]
    layouts: LayoutsDataSchema

class ActivitiesResponse(BaseModel):
    """Unified schema mapping the final response of user activities."""
    success: bool = True
    meta: ActivitiesResponseMeta
    data: ActivitiesResponseData

class MobileLogEventItem(BaseModel):
    """Individual item logging a specific mobile user interaction event."""
    activity_type: Literal["appointment", "trip"]
    activity_id: str
    event: Literal["viewed", "clicked"]
    message: Optional[str] = None
    json_data: Optional[dict] = None

class MobileLogEventsPayload(BaseModel):
    """Payload encapsulating bulk interaction log events from the driver app."""
    events: List[MobileLogEventItem]

class SimpleSuccessResponse(BaseModel):
    """Standardized simple validation response."""
    success: bool = True
    message: str


# --- HELPER SERIALIZERS ---

def serialize_ticket(t) -> dict:
    """Serializes Ticket instance to dict format."""
    return {
        "id": encode_id(t.id),
        "layout_ref": t.layout_ref,
        "content": t.content,
        "created_at": t.created_at.isoformat()
    }

def serialize_appointment(a) -> dict:
    """Serializes Appointment instance to dict format."""
    return {
        "id": encode_id(a.id),
        "type": "appointment",
        "ref": a.ref,
        "terminal_id": encode_id(a.terminal_id),
        "layout_ref": a.layout_ref,
        "status": a.status,
        "summary": a.summary,
        "license_plate": a.license_plate,
        "window_start": a.window_start.isoformat() if a.window_start else None,
        "window_end": a.window_end.isoformat() if a.window_end else None,
        "start_tolerance": a.start_tolerance,
        "end_tolerance": a.end_tolerance,
        "custom_data": a.custom_data,
        "is_safety_integration_pending": getattr(a, 'is_safety_integration_pending', None),
        "tickets": [serialize_ticket(t) for t in a.tickets]
    }

def serialize_trip(t) -> dict:
    """Serializes Trip instance to dict format."""
    return {
        "id": encode_id(t.id),
        "type": "trip",
        "ref": t.ref,
        "trucking_company_id": encode_id(t.trucking_company_id),
        "layout_ref": t.layout_ref,
        "status": t.status,
        "summary": t.summary,
        "license_plate": t.license_plate,
        "window_start": t.window_start.isoformat() if t.window_start else None,
        "window_end": t.window_end.isoformat() if t.window_end else None,
        "start_tolerance": t.start_tolerance,
        "end_tolerance": t.end_tolerance,
        "custom_data": t.custom_data,
        "from": t.from_location,
        "to": t.to_location,
        "origin": {
            "street": t.origin_street,
            "number": t.origin_number,
            "city": t.origin_city,
            "state": t.origin_state,
            "country": t.origin_country,
            "zip": t.origin_zip,
            "lat": t.origin_lat,
            "lng": t.origin_lng,
        },
        "destiny": {
            "street": t.destiny_street,
            "number": t.destiny_number,
            "city": t.destiny_city,
            "state": t.destiny_state,
            "country": t.destiny_country,
            "zip": t.destiny_zip,
            "lat": t.destiny_lat,
            "lng": t.destiny_lng,
        },
    }

def serialize_terminal(term) -> dict:
    """Serializes Terminal instance to dict format."""
    logo = None
    if term.config:
        logo = term.config.get('logo') or term.config.get('logo_url') or term.config.get('icon_url')
    return {
        "id": encode_id(term.id),
        "name": term.name,
        "branch_name": term.branch_name,
        "logo_url": logo,
        "use_remote_checkin": term.use_remote_checkin,
        "address": {
            "street": term.address_street,
            "number": term.address_number,
            "city": term.address_city,
            "state": term.address_state,
            "country": term.address_country,
            "zip": term.address_zip,
            "lat": term.address_lat,
            "lng": term.address_lng,
        },
        "geofence": term.geofence if (term.use_remote_checkin and term.geofence) else None,
        "safety_integration_active": term.config.get('safety_integration_active', False) if term.config else False,
        "safety_integration_video_url": term.config.get('safety_integration_video_url') if term.config else None,
        "safety_integration_form_url": term.config.get('safety_integration_form_url') if term.config else None,
        "safety_integration_blocks_checkin": term.config.get('safety_integration_blocks_checkin', False) if term.config else False,
    }

def serialize_trucking_company(truck) -> dict:
    """Serializes TruckingCompany instance to dict format."""
    logo = None
    if truck.config:
        logo = truck.config.get('logo') or truck.config.get('logo_url') or truck.config.get('icon_url')
    return {
        "id": encode_id(truck.id),
        "name": truck.name,
        "branch_name": truck.branch_name,
        "logo_url": logo,
        "address": {
            "city": truck.address_city,
            "state": truck.address_state,
        }
    }


# --- ROUTES ---

@router.get(
    "/activities", 
    response_model=ActivitiesResponse,
    summary="Get Mobile User Activities",
    description="Lists appointments and trips assigned to the logged-in driver. Includes pagination and layouts."
)
def get_activities(
    status_filter: str = Query("active", description="'active', 'history', ou 'all'"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches filtered appointments and trips for the mobile user.
    Loads associated companies, layouts, and ticket data.
    """
    # 1. Base Query Filters Setup
    appt_filters = [Appointment.user_tax_id == current_user.tax_id, Appointment.status != "DELETED"]
    trip_filters = [Trip.driver_id == current_user.driver_id, Trip.status != "DELETED"]

    active_statuses = ["ACTIVE", "ON_GOING", "CHECKED-IN", "CHECKED_IN", "PAUSED", "PLANNED", "IN_PROGRESS"]

    if status_filter == "active":
        # Atividades ativas: exibe apenas os status ativos
        appt_filters.append(Appointment.status.in_(active_statuses))
        trip_filters.append(Trip.status.in_(active_statuses))
    elif status_filter == "history":
        # Histórico: exibe todos os desativados e não-ativos
        appt_filters.append(Appointment.status.notin_(active_statuses))
        trip_filters.append(Trip.status.notin_(active_statuses))

    if start_date:
        appt_filters.append(Appointment.window_start >= start_date)
        trip_filters.append(Trip.window_start >= start_date)
    if end_date:
        appt_filters.append(Appointment.window_start <= end_date)
        trip_filters.append(Trip.window_start <= end_date)

    # 2. Optimized Queries (Fetching limit + 1 to determine paging availability)
    appointments = (
        db.query(Appointment)
        .options(joinedload(Appointment.tickets))
        .filter(*appt_filters)
        .order_by(Appointment.window_start.asc())
        .limit(limit + 1)
        .offset(offset)
        .all()
    )

    trips = (
        db.query(Trip)
        .filter(*trip_filters)
        .order_by(Trip.window_start.asc())
        .limit(limit + 1)
        .offset(offset)
        .all()
    )

    # paging check logic
    has_more_appointments = len(appointments) > limit
    if has_more_appointments:
        appointments = appointments[:limit]

    has_more_trips = len(trips) > limit
    if has_more_trips:
        trips = trips[:limit]

    has_more = has_more_appointments or has_more_trips

    if not appointments and not trips:
        return {
            "success": True, 
            "meta": {"has_more": False, "limit": limit, "offset": offset}, 
            "data": {
                "appointments": [], 
                "trips": [],
                "terminals": {},
                "trucking_companies": {},
                "layouts": {
                    "appointment": {},
                    "ticket": {},
                    "trip": {}
                }
            }
        }

    # 3. Aggregate unique IDs for unified data fetching
    terminal_ids = {a.terminal_id for a in appointments}
    trucking_ids = {t.trucking_company_id for t in trips}
    
    appt_layout_refs = {(a.terminal_id, a.layout_ref) for a in appointments if a.layout_ref}
    ticket_layout_refs = {(t.terminal_id, t.layout_ref) for a in appointments for t in a.tickets if t.layout_ref}
    trip_layout_refs = {(t.trucking_company_id, t.layout_ref) for t in trips if t.layout_ref}

    # 4. Fetch related companies
    terminals = db.query(Terminal).filter(Terminal.id.in_(terminal_ids)).all() if terminal_ids else []
    trucking_companies = db.query(TruckingCompany).filter(TruckingCompany.id.in_(trucking_ids)).all() if trucking_ids else []

    # 5. Fetch associated layouts
    appt_layouts = db.query(AppointmentLayout).filter(AppointmentLayout.terminal_id.in_(terminal_ids)).all() if terminal_ids else []
    ticket_layouts = db.query(TicketLayout).filter(TicketLayout.terminal_id.in_(terminal_ids)).all() if terminal_ids else []
    trip_layouts = db.query(TripLayout).filter(TripLayout.trucking_company_id.in_(trucking_ids)).all() if trucking_ids else []

    # 5.5 Fetch Safety Integrations
    safety_integrations = []
    if terminal_ids:
        safety_integrations = db.query(SafetyIntegration).filter(
            SafetyIntegration.tax_id == current_user.tax_id,
            SafetyIntegration.company_id.in_(terminal_ids)
        ).all()
    
    completed_integrations_set = set()
    now = datetime.now(timezone.utc)
    for si in safety_integrations:
        if si.expires_at is None or si.expires_at > now:
            completed_integrations_set.add(si.company_id)

    # 5.6 Inject is_safety_integration_pending into appointments
    terminals_dict = {t.id: t for t in terminals}
    for a in appointments:
        term = terminals_dict.get(a.terminal_id)
        if term and term.config and term.config.get('safety_integration_active'):
            if a.terminal_id not in completed_integrations_set:
                a.is_safety_integration_pending = True
            else:
                a.is_safety_integration_pending = False
        else:
            a.is_safety_integration_pending = False

    appt_layouts_dict = {}
    for l in appt_layouts:
        if (l.terminal_id, l.ref) in appt_layout_refs:
            appt_layouts_dict[f"{l.terminal_id}_{l.ref}"] = {"title": l.title, "layout": l.layout}

    ticket_layouts_dict = {}
    for l in ticket_layouts:
        if (l.terminal_id, l.ref) in ticket_layout_refs:
            ticket_layouts_dict[f"{l.terminal_id}_{l.ref}"] = {"title": l.title, "layout": l.layout}

    trip_layouts_dict = {}
    for l in trip_layouts:
        if (l.trucking_company_id, l.ref) in trip_layout_refs:
            trip_layouts_dict[f"{l.trucking_company_id}_{l.ref}"] = {"title": l.title, "layout": l.layout}

    # 6. Format response structure
    return {
        "success": True,
        "meta": {
            "has_more": has_more,
            "limit": limit,
            "offset": offset
        },
        "data": {
            "appointments": [serialize_appointment(a) for a in appointments],
            "trips": [serialize_trip(t) for t in trips],
            "terminals": {encode_id(term.id): serialize_terminal(term) for term in terminals},
            "trucking_companies": {encode_id(truck.id): serialize_trucking_company(truck) for truck in trucking_companies},
            "layouts": {
                "appointment": appt_layouts_dict,
                "ticket": ticket_layouts_dict,
                "trip": trip_layouts_dict
            }
        }
    }


@router.post(
    "/activities/log-events", 
    response_model=SimpleSuccessResponse,
    summary="Log Mobile Activities Events",
    description="Logs viewed/clicked events from mobile drivers for appointments and trips in batch."
)
def log_mobile_activities_events(
    payload: MobileLogEventsPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registers interactions (views or clicks) for driver app activities.
    Uses database batch queries beforehand to check record validity and ownership.
    """
    if not payload.events:
        return {"success": True, "message": "Nenhum evento enviado."}

    # Decode IDs
    appt_ids = []
    trip_ids = []
    for item in payload.events:
        try:
            if item.activity_type == "appointment":
                appt_ids.append(decode_id(item.activity_id))
            elif item.activity_type == "trip":
                trip_ids.append(decode_id(item.activity_id))
        except (ValueError, Exception):
            pass

    appts_map = {}
    if appt_ids:
        appts = db.query(Appointment).filter(
            Appointment.id.in_(appt_ids),
            Appointment.user_tax_id == current_user.tax_id
        ).all()
        appts_map = {a.id: a for a in appts}
        
    trips_map = {}
    if trip_ids:
        trips = db.query(Trip).filter(
            Trip.id.in_(trip_ids),
            Trip.driver_id == current_user.driver_id
        ).all()
        trips_map = {t.id: t for t in trips}

    for item in payload.events:
        try:
            decoded_id = decode_id(item.activity_id)
        except (ValueError, Exception):
            continue

        if item.activity_type == "appointment":
            appt = appts_map.get(decoded_id)
            if appt:
                log = AppointmentLog(
                    company_id=appt.terminal_id,
                    appointment_id=appt.id,
                    event=AppointmentEvent.VIEWED if item.event == "viewed" else AppointmentEvent.CLICKED,
                )
                db.add(log)
        elif item.activity_type == "trip":
            if trips_map.get(decoded_id):
                db.add(TripLog(
                    company_id=trips_map[decoded_id].trucking_company_id,
                    trip_id=decoded_id,
                    event=item.event,
                    message=item.message,
                    json=item.json_data
                ))

    db.commit()
    return {"success": True, "message": "Eventos logados com sucesso."}


@router.post(
    "/integrations/{terminal_id}/complete",
    response_model=SimpleSuccessResponse,
    summary="Complete Safety Integration",
    description="Registra que o motorista concluiu a integração de segurança (assistiu o vídeo ou respondeu o formulário) para um terminal específico."
)
def complete_safety_integration(
    terminal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        decoded_terminal_id = decode_id(terminal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Terminal ID inválido.")

    terminal = db.query(Terminal).filter(Terminal.id == decoded_terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal não encontrado.")

    si = db.query(SafetyIntegration).filter(
        SafetyIntegration.tax_id == current_user.tax_id,
        SafetyIntegration.company_id == decoded_terminal_id
    ).first()

    now = datetime.now(timezone.utc)
    # Default expiry: 1 year from now
    expires_at = now + timedelta(days=365)

    if not si:
        si = SafetyIntegration(
            tax_id=current_user.tax_id,
            company_id=decoded_terminal_id,
            watched_at=now,
            expires_at=expires_at
        )
        db.add(si)
    else:
        si.watched_at = now
        si.expires_at = expires_at

    try:
        db.commit()
        return {"success": True, "message": "Integração registrada com sucesso."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro ao salvar a integração de segurança.",
                "error_details": str(e)
            }
        )
