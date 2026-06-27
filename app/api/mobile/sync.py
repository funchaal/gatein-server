from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import (
    User, Appointment, Trip, Terminal, TruckingCompany, 
    AppointmentLayout, TicketLayout, TripLayout
)

router = APIRouter()

@router.get("/activities")
def get_activities(
    status_filter: str = Query("active", description="'active', 'history', ou 'all'"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Configuração dos Filtros Base
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

    # 2. Buscas Otimizadas (Buscando limit + 1 para verificar se há mais dados)
    appointments = (
        db.query(Appointment)
        .options(joinedload(Appointment.tickets))
        .filter(*appt_filters)
        .order_by(Appointment.schedule_start_time.asc())
        .limit(limit + 1) # Adiciona 1 ao limite
        .offset(offset)
        .all()
    )

    trips = (
        db.query(Trip)
        .filter(*trip_filters)
        .order_by(Trip.schedule_start_time.asc())
        .limit(limit + 1) # Adiciona 1 ao limite
        .offset(offset)
        .all()
    )

    # Lógica do has_more: se veio mais do que o limite, tem mais página.
    has_more_appointments = len(appointments) > limit
    if has_more_appointments:
        appointments = appointments[:limit] # Corta o registro extra

    has_more_trips = len(trips) > limit
    if has_more_trips:
        trips = trips[:limit] # Corta o registro extra

    has_more = has_more_appointments or has_more_trips

    if not appointments and not trips:
        return {"success": True, "meta": {"has_more": False}, "data": {"appointments": [], "trips": []}}

    # 3. Coleta de IDs Únicos para Carregamento Normalizado
    terminal_ids = {a.terminal_id for a in appointments}
    trucking_ids = {t.trucking_company_id for t in trips}
    
    appt_layout_refs = {(a.terminal_id, a.layout_ref) for a in appointments if a.layout_ref}
    ticket_layout_refs = {(t.terminal_id, t.layout_ref) for a in appointments for t in a.tickets if t.layout_ref}
    trip_layout_refs = {(t.trucking_company_id, t.layout_ref) for t in trips if t.layout_ref}

    # 4. Busca de Entidades Relacionadas (Empresas)
    terminals = db.query(Terminal).filter(Terminal.id.in_(terminal_ids)).all() if terminal_ids else []
    trucking_companies = db.query(TruckingCompany).filter(TruckingCompany.id.in_(trucking_ids)).all() if trucking_ids else []

    # 5. Busca de Layouts
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

    # 6. Formatação dos Dados (Mantendo a estrutura normalizada para o Redux)
    # 6. Formatação dos Dados
    return {
        "success": True,
        "meta": {
            "has_more": has_more,
            "limit": limit,
            "offset": offset
        },
        "data": {
            "appointments": [
                {
                    "id": str(a.id),
                    "type": "appointment",
                    "ref": a.ref,
                    "terminal_id": str(a.terminal_id),
                    "layout_ref": a.layout_ref,
                    "operation_type": a.operation_type,
                    "status": a.status,
                    "summary": a.summary,
                    "vehicle_plate": a.vehicle_plate,
                    "schedule_start_time": a.schedule_start_time.isoformat() if a.schedule_start_time else None,
                    "schedule_end_time": a.schedule_end_time.isoformat() if a.schedule_end_time else None,
                    "schedule_start_tolerance_min": a.schedule_start_tolerance_min,
                    "schedule_end_tolerance_min": a.schedule_end_tolerance_min,
                    "custom_data": a.custom_data,
                    "tickets": [
                        {
                            "id": str(t.id),
                            "layout_ref": t.layout_ref,
                            "content": t.content,
                            "created_at": t.created_at.isoformat()
                        } for t in a.tickets
                    ]
                } for a in appointments
            ],
            "trips": [
                {
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
                    "schedule_start_tolerance_min": t.schedule_start_tolerance_min,
                    "schedule_end_tolerance_min": t.schedule_end_tolerance_min,
                    "custom_data": t.custom_data,
                } for t in trips
            ],
            "terminals": {
                str(term.id): {
                    "id": str(term.id),
                    "name": term.name,
                    "use_remote_checkin": term.use_remote_checkin,
                    "address": {
                        "street": term.address_street,
                        "city": term.address_city,
                        "lat": term.address_lat,
                        "lng": term.address_lng,
                    },
                    "geofence": term.geofence if (term.use_remote_checkin and term.geofence) else None,
                } for term in terminals
            },
            "trucking_companies": {
                str(truck.id): {
                    "name": truck.name,
                    "address": {
                        "city": truck.address_city,
                        "state": truck.address_state,
                    }
                } for truck in trucking_companies
            },
            "layouts": {
                "appointment": appt_layouts_dict,
                "ticket": ticket_layouts_dict,
                "trip": trip_layouts_dict
            }
        }
    }