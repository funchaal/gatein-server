from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, Company, Terminal, TruckingCompany

router = APIRouter()

# --- Schemas Pydantic ---

class GeofenceUpdateRequest(BaseModel):
    geofence: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None

class CompanyInfoUpdateRequest(BaseModel):
    name: Optional[str] = None
    use_remote_checkin: Optional[bool] = None
    geofence: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None


# --- Endpoints de Empresa e Geofence ---

@router.get("/geofence")
def get_geofence(
    current_user: CompanyUser = Depends(require_permission('geofence', 'read')),
    db: Session = Depends(get_db)
):

    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    # Geofence só existe para Terminais
    geofence_data = company.geofence if isinstance(company, Terminal) else {}

    return {"success": True, "data": {
        "geofence": geofence_data,
        "address": {
            "street": company.address_street,
            "number": company.address_number,
            "city": company.address_city,
            "state": company.address_state,
            "country": company.address_country,
            "zip": company.address_zip,
            "lat": company.address_lat,
            "lng": company.address_lng,
        },
    }}


@router.put("/geofence")
def update_geofence(
    body: GeofenceUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('geofence', 'write')),
    db: Session = Depends(get_db)
):

    company = db.query(Company).get(current_user.company_id)
    
    if body.geofence is not None:
        if not isinstance(company, Terminal):
            raise HTTPException(
                status_code=400, 
                detail={"code": "INVALID_COMPANY_TYPE", "message": "Apenas terminais possuem geofence."}
            )
        company.geofence = body.geofence

    if body.address is not None:
        addr = body.address
        company.address_street  = addr.get("street",  company.address_street)
        company.address_number  = addr.get("number",  company.address_number)
        company.address_city    = addr.get("city",    company.address_city)
        company.address_state   = addr.get("state",   company.address_state)
        company.address_country = addr.get("country", company.address_country)
        company.address_zip     = addr.get("zip",     company.address_zip)
        company.address_lat     = addr.get("lat",     company.address_lat)
        company.address_lng     = addr.get("lng",     company.address_lng)

    try:
        db.commit()
        return {"success": True, "data": {"updated": True}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.get("/company/info")
def get_company_info(
    current_user: CompanyUser = Depends(require_permission('company_information', 'read')),
    db: Session = Depends(get_db)
):

    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    data = {
        "id": str(company.id),
        "type": company.type,
        "name": company.name,
        "tax_id": company.tax_id,
        "address": {
            "street": company.address_street,
            "number": company.address_number,
            "city": company.address_city,
            "state": company.address_state,
            "country": company.address_country,
            "zip": company.address_zip,
            "lat": company.address_lat,
            "lng": company.address_lng,
        }
    }

    if isinstance(company, Terminal):
        data["use_remote_checkin"] = company.use_remote_checkin
        data["geofence"] = company.geofence

    return {"success": True, "data": data}


@router.put("/company/info")
def update_company_info(
    body: CompanyInfoUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('company_information', 'write')),
    db: Session = Depends(get_db)
):

    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    if body.name is not None:
        company.name = body.name

    if isinstance(company, Terminal):
        if body.use_remote_checkin is not None:
            company.use_remote_checkin = body.use_remote_checkin
        if body.geofence is not None:
            company.geofence = body.geofence

    if body.address is not None:
        addr = body.address
        company.address_street  = addr.get("street",  company.address_street)
        company.address_number  = addr.get("number",  company.address_number)
        company.address_city    = addr.get("city",    company.address_city)
        company.address_state   = addr.get("state",   company.address_state)
        company.address_country = addr.get("country", company.address_country)
        company.address_zip     = addr.get("zip",     company.address_zip)
        company.address_lat     = addr.get("lat",     company.address_lat)
        company.address_lng     = addr.get("lng",     company.address_lng)

    try:
        db.commit()
        return {"success": True, "message": "Dados da empresa atualizados com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})