import uuid
import math
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case, cast, Float

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Company, User, Appointment, Trip, Terminal

router = APIRouter()

# --- SCHEMAS (Pydantic Response Models) ---

class CompanyAddressSchema(BaseModel):
    """Schema representing structured address properties of a company."""
    street: Optional[str] = None
    number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class MobileCompanyResponseSchema(BaseModel):
    """Schema mapping serialized company attributes for mobile devices."""
    id: str
    name: str
    branch_name: Optional[str] = None
    type: str
    tax_id: str
    unit_code: Optional[str] = None
    phone: str
    email: str
    logo_url: Optional[str] = None
    address: CompanyAddressSchema
    geofence: Optional[Dict[str, Any]] = None
    distance_km: Optional[float] = None
    appointment_count: int = 0
    trip_count: int = 0


# --- HELPERS ---

def serialize_company(company, distance_km=None, appointment_count=0, trip_count=0) -> dict:
    """
    Utility serializer mapping database Company instances to mobile-friendly JSON dict formats.
    Loads nested address, logo mappings, geofences, and activity aggregations.
    """
    geofence_data = getattr(company, 'geofence', None)
    logo = None
    if company.config:
        logo = company.config.get('logo') or company.config.get('logo_url') or company.config.get('icon_url')
    
    return {
        "id": str(company.id),
        "name": company.name,
        "branch_name": company.branch_name,
        "type": company.type,
        "tax_id": company.tax_id,
        "unit_code": company.unit_code,
        "phone": company.phone,
        "email": company.email,
        "logo_url": logo,
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


# --- ROUTES ---

@router.get(
    "/companies/search", 
    response_model=List[MobileCompanyResponseSchema],
    summary="Search Companies",
    description="Finds companies by partial name or branch title with optional geolocation distance calculations."
)
def search_companies(
    q: str = Query(None, min_length=2),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Filters companies by searching text queries against normalized unaccented title values.
    Calculates distances using Haversine formulas in PostgreSQL if geographic coordinates are provided.
    """
    if not q or len(q.strip()) < 2: 
        return []

    # Apply f_unaccent function to search concatenated title properties
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


@router.get(
    "/companies/nearby", 
    response_model=List[MobileCompanyResponseSchema],
    summary="Get Nearby Companies",
    description="Queries companies located within a specified radius (in km) from current driver position."
)
def get_nearby_companies(
    lat: float = Query(..., description="Latitude atual do usuário"),
    lng: float = Query(..., description="Longitude atual do usuário"),
    radius_km: float = Query(10.0, description="Raio máximo de busca em quilômetros"),
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Computes spatial distance using high-precision Haversine queries on the DB layer.
    """
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Coordenadas inválidas.")

    # Earth Radius constant
    EARTH_RADIUS_KM = 6371.0
    TerminalTable = Terminal.__table__

    # Resolve effective coordinates (prioritize Geofence center over default address coordinates)
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

    # Core Haversine formula calculation
    math_expr = (
        func.sin(user_lat_rad) * func.sin(lat_rad) +
        func.cos(user_lat_rad) * func.cos(lat_rad) * func.cos(lng_rad - user_lng_rad)
    )

    distance_expr = EARTH_RADIUS_KM * func.acos(func.least(1.0, math_expr))

    # Build query mapping
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


@router.get(
    "/companies/initial", 
    response_model=List[MobileCompanyResponseSchema],
    summary="Get Initial Landing Companies List",
    description="Generates a customized dashboard companies list containing recent activities and 10 closest terminals."
)
def get_initial_companies(
    lat: Optional[float] = Query(None, description="Latitude atual do usuário"),
    lng: Optional[float] = Query(None, description="Longitude atual do usuário"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Constructs the landing dashboard list. Exposes recent companies from user's appointments and trips
    combined with nearest companies sorted by geolocation.
    """
    # 1. Fetch user appointments and count occurrences
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
            
    # 2. Fetch user trips and count occurrences
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
        
    # 3. Combine appointments and trips to sort by recent activities
    combined = []
    for a in appointments:
        if a.terminal_id and a.schedule_start_time:
            combined.append((a.terminal_id, a.schedule_start_time))
    for t in trips:
        if t.trucking_company_id and t.schedule_start_time:
            combined.append((t.trucking_company_id, t.schedule_start_time))
            
    combined.sort(key=lambda x: x[1], reverse=True)
    
    # Select top 5 unique recent companies
    recent_company_ids = []
    seen = set()
    for company_id, _ in combined:
        if company_id not in seen:
            seen.add(company_id)
            recent_company_ids.append(company_id)
            if len(recent_company_ids) == 5:
                break
                
    recent_companies = []
    if recent_company_ids:
        companies_map = {
            c.id: c for c in db.query(Company).filter(Company.id.in_(recent_company_ids)).all()
        }
        recent_companies = [companies_map[cid] for cid in recent_company_ids if cid in companies_map]
        
    # 4. Fetch 10 closest companies by geolocation
    nearby_companies = []
    nearby_distances = {}
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise HTTPException(status_code=400, detail="Coordenadas inválidas.")
            
        TerminalTable = Terminal.__table__

        # Resolve coordinates prioritizations
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
        
    # 5. Format unified landing responses
    response = []
    recent_ids_set = set(recent_company_ids)
    
    # Python-level helper to calculate Haversine distance
    def calculate_haversine(lat1, lng1, lat2, lng2):
        rad = 3.141592653589793 / 180.0
        dlat = (lat2 - lat1) * rad
        dlng = (lng2 - lng1) * rad
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlng / 2) ** 2)
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        return 6371.0 * c
        
    # Add recent companies first
    for rc in recent_companies:
        dist = None
        if rc.id in nearby_distances:
            dist = round(nearby_distances[rc.id], 2)
        elif lat is not None and lng is not None:
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
        
    # Add closest companies that are not already present in the recents list
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