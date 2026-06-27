import uuid
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case, cast, Float
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Company, User, Appointment, Trip, Terminal

router = APIRouter()

def serialize_company(company, distance_km=None, appointment_count=0, trip_count=0):
    geofence_data = getattr(company, 'geofence', None)
    
    return {
        "id": str(company.id),
        "name": company.name,
        "branch_name": company.branch_name,
        "type": company.type,
        "tax_id": company.tax_id,
        "unit_code": company.unit_code,
        "phone": company.phone,
        "email": company.email,
        "logo_url": company.config.get('logo') or company.config.get('logo_url') or company.config.get('icon_url'),
        "address": {
            "street": company.address_street,
            "number": company.address_number,
            "city": company.address_city,
            "state": company.address_state,
            "country": company.address_country,
            "zip": company.address_zip,
            "lat": company.address_lat,
            "lng": company.address_lng
        },
        "geofence": geofence_data,
        "distance_km": distance_km,
        "appointment_count": appointment_count,
        "trip_count": trip_count
    }

@router.get("/companies/search")
def search_companies(
    q: str = Query(None, min_length=2),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    if not q or len(q.strip()) < 2: 
        return []

    # 1. Aplicamos o f_unaccent na concatenação das colunas
    search_vector = func.f_unaccent(
        func.concat(Company.name, ' ', func.coalesce(Company.branch_name, ''))
    )

    termos = q.strip().split()
    condicoes = [search_vector.ilike(func.f_unaccent(f"%{termo}%")) for termo in termos]

    distance_col = None
    TerminalTable = Terminal.__table__
    if lat is not None and lng is not None:
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
        distance_col = (6371.0 * func.acos(func.least(1.0, math_expr))).label("distance_km")

    if distance_col is not None:
        stmt = select(
            Company,
            distance_col
        ).outerjoin(TerminalTable, Company.id == TerminalTable.c.id).filter(
            and_(*condicoes)
        ).limit(20)
        resultados = db.execute(stmt).all()
        return [
            serialize_company(r[0], distance_km=round(r[1], 2) if r[1] is not None else None)
            for r in resultados
        ]
    else:
        stmt = select(Company).filter(and_(*condicoes)).limit(20)
        resultados = db.scalars(stmt).all()
        return [serialize_company(r) for r in resultados]

@router.get("/companies/nearby")
def get_nearby_companies(
    lat: float = Query(..., description="Latitude atual do usuário"),
    lng: float = Query(..., description="Longitude atual do usuário"),
    radius_km: float = Query(10.0, description="Raio máximo de busca em quilômetros"),
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # 1. Validação básica de coordenadas
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Coordenadas inválidas.")

    # Raio da Terra em quilômetros
    EARTH_RADIUS_KM = 6371.0
    
    TerminalTable = Terminal.__table__

    # Resolução de coordenadas efetivas (Geofence -> Endereço)
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

    # Cálculo do núcleo da Fórmula de Haversine
    math_expr = (
        func.sin(user_lat_rad) * func.sin(lat_rad) +
        func.cos(user_lat_rad) * func.cos(lat_rad) * func.cos(lng_rad - user_lng_rad)
    )

    distance_expr = EARTH_RADIUS_KM * func.acos(func.least(1.0, math_expr))

    # Construção da Query
    stmt = select(
        Company,
        distance_expr.label("distance_km")
    ).outerjoin(TerminalTable, Company.id == TerminalTable.c.id).filter(
        effective_lat.isnot(None),
        effective_lng.isnot(None),
        distance_expr <= radius_km
    ).order_by(
        distance_expr.asc()
    ).limit(50)

    resultados = db.execute(stmt).all()

    return [
        serialize_company(
            r[0],
            distance_km=round(r[1], 2) if r[1] is not None else None
        ) for r in resultados
    ]

@router.get("/companies/initial")
def get_initial_companies(
    lat: Optional[float] = Query(None, description="Latitude atual do usuário"),
    lng: Optional[float] = Query(None, description="Longitude atual do usuário"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Obter todos os compromissos (appointments) do usuário e contar por terminal
    appointments = (
        db.query(Appointment)
        .filter(Appointment.user_tax_id == current_user.tax_id, Appointment.status != "DELETED")
        .order_by(Appointment.schedule_start_time.desc())
        .all()
    )
    
    appointment_counts = {}
    for a in appointments:
        if a.terminal_id:
            appointment_counts[a.terminal_id] = appointment_counts.get(a.terminal_id, 0) + 1
            
    # 2. Obter todas as viagens (trips) do usuário e contar por transportadora
    trips = []
    if current_user.driver_id:
        trips = (
            db.query(Trip)
            .filter(Trip.driver_id == current_user.driver_id, Trip.status != "DELETED")
            .order_by(Trip.schedule_start_time.desc())
            .all()
        )
        
    trip_counts = {}
    for t in trips:
        if t.trucking_company_id:
            trip_counts[t.trucking_company_id] = trip_counts.get(t.trucking_company_id, 0) + 1
        
    # 3. Mesclar compromissos e viagens para ordenar cronologicamente por atividade recente
    combined = []
    for a in appointments:
        if a.terminal_id and a.schedule_start_time:
            combined.append((a.terminal_id, a.schedule_start_time))
    for t in trips:
        if t.trucking_company_id and t.schedule_start_time:
            combined.append((t.trucking_company_id, t.schedule_start_time))
            
    # Ordenar por data decrescente
    combined.sort(key=lambda x: x[1], reverse=True)
    
    # Selecionar as primeiras 5 empresas únicas
    recent_company_ids = []
    seen = set()
    for company_id, _ in combined:
        if company_id not in seen:
            seen.add(company_id)
            recent_company_ids.append(company_id)
            if len(recent_company_ids) == 5:
                break
                
    # Buscar os dados destas empresas recentes
    recent_companies = []
    if recent_company_ids:
        companies_map = {
            c.id: c for c in db.query(Company).filter(Company.id.in_(recent_company_ids)).all()
        }
        recent_companies = [companies_map[cid] for cid in recent_company_ids if cid in companies_map]
        
    # 4. Obter as 10 empresas mais próximas por geolocalização (sem filtrar as recentes)
    nearby_companies = []
    nearby_distances = {}
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise HTTPException(status_code=400, detail="Coordenadas inválidas.")
            
        TerminalTable = Terminal.__table__

        # Resolução de coordenadas efetivas (Geofence -> Endereço)
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
        
        stmt = select(
            Company,
            distance_expr.label("distance_km")
        ).outerjoin(TerminalTable, Company.id == TerminalTable.c.id).filter(
            effective_lat.isnot(None),
            effective_lng.isnot(None)
        ).order_by(
            distance_expr.asc()
        ).limit(10)
        
        resultados = db.execute(stmt).all()
        nearby_companies = resultados
        nearby_distances = {r[0].id: r[1] for r in resultados}
        
    # 5. Formatar a resposta final unificada
    response = []
    recent_ids_set = set(recent_company_ids)
    
    # Helper em Python para calcular distância Haversine
    def calculate_haversine(lat1, lng1, lat2, lng2):
        rad = 3.141592653589793 / 180.0
        dlat = (lat2 - lat1) * rad
        dlng = (lng2 - lng1) * rad
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlng / 2) ** 2)
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        return 6371.0 * c
        
    # Adicionar recentes primeiro
    for rc in recent_companies:
        dist = None
        # Opcionalmente calcula/retorna distância se a empresa estiver entre as 10 mais próximas
        if rc.id in nearby_distances:
            dist = round(nearby_distances[rc.id], 2)
        elif lat is not None and lng is not None:
            # Se não está nas 10 mais próximas, calcula manualmente com base na geofence ou endereço
            comp_lat = None
            comp_lng = None
            if rc.type == 'terminal' and hasattr(rc, 'geofence') and rc.geofence:
                center = rc.geofence.get('center', {})
                if center and 'lat' in center and 'lng' in center:
                    comp_lat = center['lat']
                    comp_lng = center['lng']
            
            if comp_lat is None or comp_lng is None:
                comp_lat = rc.address_lat
                comp_lng = rc.address_lng
                
            if comp_lat is not None and comp_lng is not None:
                dist = round(calculate_haversine(lat, lng, comp_lat, comp_lng), 2)
            
        response.append(
            serialize_company(
                rc,
                distance_km=dist,
                appointment_count=appointment_counts.get(rc.id, 0),
                trip_count=trip_counts.get(rc.id, 0)
            )
        )
        
    # Adicionar as 10 mais próximas que não estão nas recentes
    for nc in nearby_companies:
        if nc[0].id not in recent_ids_set:
            response.append(
                serialize_company(
                    nc[0],
                    distance_km=round(nc[1], 2) if nc[1] is not None else None,
                    appointment_count=0,
                    trip_count=0
                )
            )
            
    return response