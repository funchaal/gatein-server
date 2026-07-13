import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, case, cast, Float

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Company, Terminal, Appointment, Trip, Announcement, AnnouncementLog

router = APIRouter()

# --- SCHEMAS ---

class MobileAnnouncementResponseData(BaseModel):
    """Schema representing details of an announcement for mobile display."""
    id: str
    company_id: str
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    image_position: Dict[str, Any]
    company_name: str
    company_branch_name: Optional[str]
    company_logo_url: Optional[str]

class MobileAnnouncementListResponse(BaseModel):
    """Schema representing the list response of active announcements."""
    success: bool = True
    data: List[MobileAnnouncementResponseData]

class SimpleSuccessResponse(BaseModel):
    """Standardized response indicating a successful request with a message."""
    success: bool = True
    message: str

class MobileAnnouncementLogEventItem(BaseModel):
    """Individual event parameter mapping an announcement interaction trace."""
    announcement_id: uuid.UUID
    event: Literal["viewed"]
    message: Optional[str] = None
    json_data: Optional[dict] = None

class MobileAnnouncementLogEventsPayload(BaseModel):
    """Payload encapsulating bulk announcement logging events."""
    events: List[MobileAnnouncementLogEventItem]


# --- ROTAS ---

@router.get(
    "/announcements", 
    response_model=MobileAnnouncementListResponse,
    summary="Get Active Announcements",
    description="Returns active announcements for companies matching user appointments, trips, or within 50km radius."
)
def get_mobile_announcements(
    lat: Optional[float] = Query(None, description="Latitude atual do usuário"),
    lng: Optional[float] = Query(None, description="Longitude atual do usuário"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves and filters active announcements for the logged-in mobile driver.
    """
    # 1. Obter todas as empresas onde o usuário tem agendamentos (não deletados)
    appointments = db.query(Appointment).filter(
        Appointment.user_tax_id == current_user.tax_id,
        Appointment.status != "DELETED"
    ).all()
    
    company_ids = {a.terminal_id for a in appointments if a.terminal_id}

    # 2. Obter todas as empresas onde o motorista tem viagens (não deletadas)
    if current_user.driver_id:
        trips = db.query(Trip).filter(
            Trip.driver_id == current_user.driver_id,
            Trip.status != "DELETED"
        ).all()
        for t in trips:
            if t.trucking_company_id:
                company_ids.add(t.trucking_company_id)

    # 3. Se houver coordenadas, buscar empresas em um raio de 50km
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise HTTPException(status_code=400, detail="Coordenadas inválidas.")

        TerminalTable = Terminal.__table__

        # Resolução de coordenadas efetivas
        effective_lat = case(
            (
                and_(
                    Company.type == 'terminal',
                    TerminalTable.c.geofence['center']['lat'].astext.isnot(None)
                ),
                cast(TerminalTable.c.geofence['center']['lat'].astext, Float)
            ),
            else_=Company.address_lat
        )
        
        effective_lng = case(
            (
                and_(
                    Company.type == 'terminal',
                    TerminalTable.c.geofence['center']['lng'].astext.isnot(None)
                ),
                cast(TerminalTable.c.geofence['center']['lng'].astext, Float)
            ),
            else_=Company.address_lng
        )

        lat_rad = func.radians(effective_lat)
        lng_rad = func.radians(effective_lng)
        user_lat_rad = func.radians(lat)
        user_lng_rad = func.radians(lng)

        math_expr = (
            func.sin(user_lat_rad) * func.sin(lat_rad) +
            func.cos(user_lat_rad) * func.cos(lat_rad) * func.cos(lng_rad - user_lng_rad)
        )
        distance_expr = 6371.0 * func.acos(func.least(1.0, math_expr))

        stmt = select(Company.id).outerjoin(
            TerminalTable, Company.id == TerminalTable.c.id
        ).filter(
            effective_lat.isnot(None),
            effective_lng.isnot(None),
            distance_expr <= 50.0  # Raio de 50km
        )

        nearby_ids = db.execute(stmt).scalars().all()
        for nid in nearby_ids:
            if nid:
                company_ids.add(nid)

    # 4. Buscar avisos ativos para o conjunto de empresas encontradas
    now = datetime.now(timezone.utc)
    
    # Se a lista de empresas estiver vazia, não há avisos para retornar
    if not company_ids:
        return {"success": True, "data": []}

    announcements = db.query(Announcement).join(
        Company, Announcement.company_id == Company.id
    ).filter(
        Announcement.company_id.in_(list(company_ids)),
        Announcement.is_active == True,
        or_(Announcement.start_at.is_(None), Announcement.start_at <= now),
        or_(Announcement.end_at.is_(None), Announcement.end_at >= now)
    ).order_by(Announcement.created_at.desc()).all()

    # 5. Formatar a resposta
    response_data = []
    for a in announcements:
        comp = a.company
        logo = None
        if comp and comp.config:
            logo = comp.config.get('logo') or comp.config.get('logo_url') or comp.config.get('icon_url')
            
        response_data.append({
            "id": str(a.id),
            "company_id": str(a.company_id),
            "title": a.title,
            "subtitle": a.subtitle,
            "description": a.description,
            "image_url": a.image_url,
            "image_position": a.image_position or {"x": 50, "y": 50},
            "company_name": comp.name if comp else "",
            "company_branch_name": comp.branch_name if comp else None,
            "company_logo_url": logo
        })

    return {"success": True, "data": response_data}


@router.post(
    "/announcements/log-events",
    response_model=SimpleSuccessResponse,
    summary="Log Announcement Events",
    description="Registers viewing events of announcements on the mobile driver app."
)
def log_mobile_announcement_events(
    payload: MobileAnnouncementLogEventsPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logs viewed interaction for announcements in batch mode.
    Pre-queries announcement records in a single batch query for efficiency.
    """
    if not payload.events:
        return {"success": True, "message": "Nenhum evento enviado."}

    # Batch query announcements to optimize database hits
    ann_ids = [item.announcement_id for item in payload.events]
    existing_anns = db.query(Announcement).filter(Announcement.id.in_(ann_ids)).all() if ann_ids else []
    ann_map = {a.id: a for a in existing_anns}

    for item in payload.events:
        ann = ann_map.get(item.announcement_id)
        if ann:
            log = AnnouncementLog(
                announcement_id=ann.id,
                user_id=current_user.id,
                event=item.event,
                message=item.message or "Aviso visualizado no app móvel.",
                json=item.json_data or {}
            )
            db.add(log)

    db.commit()
    return {"success": True, "message": "Eventos de avisos registrados com sucesso."}
