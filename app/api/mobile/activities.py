import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import (
    User, Appointment, Trip, Terminal, TruckingCompany, 
    AppointmentLayout, TicketLayout, TripLayout, AppointmentLog, TripLog
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
    vehicle_plate: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    schedule_start_tolerance: int
    schedule_end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
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
    vehicle_plate: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    schedule_start_tolerance: int
    schedule_end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
    from_: Optional[str] = Field(None, serialization_alias="from", validation_alias="from")
    to: Optional[str] = None
    origin: AddressSchema
    destiny: AddressSchema

class TerminalResponseSchema(BaseModel):
    """Schema representing terminal company details."""
    id: str
    name: str
    use_remote_checkin: bool
    address: AddressSchema
    geofence: Optional[Dict[str, Any]] = None

class TruckingCompanyResponseSchema(BaseModel):
    """Schema representing trucking company details."""
    name: str
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
    activity_id: uuid.UUID
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
        "id": str(t.id),
        "layout_ref": t.layout_ref,
        "content": t.content,
        "created_at": t.created_at.isoformat()
    }

def serialize_appointment(a) -> dict:
    """Serializes Appointment instance to dict format."""
    return {
        "id": str(a.id),
        "type": "appointment",
        "ref": a.ref,
        "terminal_id": str(a.terminal_id),
        "layout_ref": a.layout_ref,
        "status": a.status,
        "summary": a.summary,
        "vehicle_plate": a.vehicle_plate,
        "schedule_start_time": a.schedule_start_time.isoformat() if a.schedule_start_time else None,
        "schedule_end_time": a.schedule_end_time.isoformat() if a.schedule_end_time else None,
        "schedule_start_tolerance": a.schedule_start_tolerance,
        "schedule_end_tolerance": a.schedule_end_tolerance,
        "custom_data": a.custom_data,
        "tickets": [serialize_ticket(t) for t in a.tickets]
    }

def serialize_trip(t) -> dict:
    """Serializes Trip instance to dict format."""
    return {
        "id": str(t.id),
        "type": "trip",
        "ref": t.ref,
        "trucking_company_id": str(t.trucking_company_id),
        "layout_ref": t.layout_ref,
        "status": t.status,
        "summary": t.summary,
        "vehicle_plate": t.vehicle_plate,
        "schedule_start_time": t.schedule_start_time.isoformat() if t.schedule_start_time else None,
        "schedule_end_time": t.schedule_end_time.isoformat() if t.schedule_end_time else None,
        "schedule_start_tolerance": t.schedule_start_tolerance,
        "schedule_end_tolerance": t.schedule_end_tolerance,
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
    return {
        "id": str(term.id),
        "name": term.name,
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
    }

def serialize_trucking_company(truck) -> dict:
    """Serializes TruckingCompany instance to dict format."""
    return {
        "name": truck.name,
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

    if status_filter == "active":
        active_statuses = ["SCHEDULED", "IN_PROGRESS", "CHECKED_IN", "PLANNED"]
        appt_filters.append(Appointment.status.in_(active_statuses))
        trip_filters.append(Trip.status.in_(active_statuses))
    elif status_filter == "history":
        history_statuses = ["COMPLETED", "CANCELLED", "NO_SHOW"]
        appt_filters.append(Appointment.status.in_(history_statuses))
        trip_filters.append(Trip.status.in_(history_statuses))

    if start_date:
        appt_filters.append(Appointment.schedule_start_time >= start_date)
        trip_filters.append(Trip.schedule_start_time >= start_date)
    if end_date:
        appt_filters.append(Appointment.schedule_start_time <= end_date)
        trip_filters.append(Trip.schedule_start_time <= end_date)

    # 2. Optimized Queries (Fetching limit + 1 to determine paging availability)
    appointments = (
        db.query(Appointment)
        .options(joinedload(Appointment.tickets))
        .filter(*appt_filters)
        .order_by(Appointment.schedule_start_time.asc())
        .limit(limit + 1)
        .offset(offset)
        .all()
    )

    trips = (
        db.query(Trip)
        .filter(*trip_filters)
        .order_by(Trip.schedule_start_time.asc())
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
            "terminals": {str(term.id): serialize_terminal(term) for term in terminals},
            "trucking_companies": {str(truck.id): serialize_trucking_company(truck) for truck in trucking_companies},
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

    # Gather activity IDs by type to query in batch
    appt_ids = [item.activity_id for item in payload.events if item.activity_type == "appointment"]
    trip_ids = [item.activity_id for item in payload.events if item.activity_type == "trip"]
    
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
        if item.activity_type == "appointment":
            appt = appts_map.get(item.activity_id)
            if appt:
                log = AppointmentLog(
                    company_id=appt.terminal_id,
                    appointment_id=appt.id,
                    event=item.event,
                    message=item.message or f"Agendamento {item.event} no app móvel.",
                    json=item.json_data or {}
                )
                db.add(log)
        elif item.activity_type == "trip":
            trip = trips_map.get(item.activity_id)
            if trip:
                log = TripLog(
                    company_id=trip.trucking_company_id,
                    trip_id=trip.id,
                    event=item.event,
                    message=item.message or f"Viagem {item.event} no app móvel.",
                    json=item.json_data or {}
                )
                db.add(log)
                
    db.commit()
    return {"success": True, "message": "Eventos registrados com sucesso."}

