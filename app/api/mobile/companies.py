import uuid
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Company, User

router = APIRouter()

@router.get("/companies/search")
def search_companies(
    q: str = Query(None, min_length=2), 
    db: Session = Depends(get_db)
):
    if not q or len(q.strip()) < 2: 
        return []

    # 1. Aplicamos o f_unaccent na concatenação das colunas
    search_vector = func.f_unaccent(
        func.concat(Company.name, ' ', func.coalesce(Company.branch_name, ''))
    )

    termos = q.strip().split()

    # 2. Aplicamos o f_unaccent também no que o usuário digitou!
    # Assim o banco compara "portuario" com "portuario"
    condicoes = [search_vector.ilike(func.f_unaccent(f"%{termo}%")) for termo in termos]

    stmt = select(
        Company.id, Company.name, Company.branch_name, 
        Company.unit_code, Company.type, Company.tax_id
    ).filter(
        and_(*condicoes)
    ).limit(20)

    resultados = db.execute(stmt).all()
    
    return [
        {
            "id": r.id, 
            "name": r.name, 
            "branch_name": r.branch_name, 
            "unit_code": r.unit_code,
            "type": r.type, 
            "tax_id": r.tax_id
        } for r in resultados
    ]

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

    # 2. Converte as coordenadas do banco (graus) para radianos
    lat_rad = func.radians(Company.address_lat)
    lng_rad = func.radians(Company.address_lng)
    
    # 3. Converte as coordenadas recebidas na API (graus) para radianos
    user_lat_rad = func.radians(lat)
    user_lng_rad = func.radians(lng)

    # 4. Cálculo do núcleo da Fórmula de Haversine
    math_expr = (
        func.sin(user_lat_rad) * func.sin(lat_rad) +
        func.cos(user_lat_rad) * func.cos(lat_rad) * func.cos(lng_rad - user_lng_rad)
    )

    # 5. Expressão final da distância
    # O func.least(1.0, ...) é um truque de segurança crucial. 
    # Em pontos exatos (distância zero), erros de precisão do Float podem gerar 
    # um número como 1.0000000002, o que quebra a função acos() no banco de dados.
    distance_expr = EARTH_RADIUS_KM * func.acos(func.least(1.0, math_expr))

    # 6. Construção da Query
    stmt = select(
        Company.id,
        Company.name,
        Company.branch_name,
        Company.type,
        Company.address_lat,
        Company.address_lng,
        distance_expr.label("distance_km") # Nomeamos a coluna calculada para capturá-la depois
    ).filter(
        Company.address_lat.isnot(None), # Ignora empresas sem localização cadastrada
        Company.address_lng.isnot(None),
        distance_expr <= radius_km       # O filtro principal: apenas dentro do raio solicitado
    ).order_by(
        distance_expr.asc()              # Ordena da mais próxima para a mais distante
    ).limit(50)                          # Limite para não sobrecarregar o App

    # 7. Execução
    resultados = db.execute(stmt).all()

    # 8. Retorno serializado
    return [
        {
            "id": r.id,
            "name": r.name,
            "branch_name": r.branch_name,
            "type": r.type, 
            "tax_id": r.tax_id,
            # Arredondamos a distância para 2 casas decimais (ex: 2.45 km)
            "distance_km": round(r.distance_km, 2) 
        } for r in resultados
    ]