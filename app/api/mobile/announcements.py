import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, case, cast, Float

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Company, Terminal, Appointment, Trip, Announcement

router = APIRouter()

# --- SCHEMAS ---

class MobileAnnouncementResponseData(BaseModel):
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
    success: bool = True
    data: List[MobileAnnouncementResponseData]


# --- ROTAS ---

@router.get("/announcements", response_model=MobileAnnouncementListResponse)
def get_mobile_announcements(
    lat: Optional[float] = Query(None, description="Latitude atual do usuário"),
    lng: Optional[float] = Query(None, description="Longitude atual do usuário"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
