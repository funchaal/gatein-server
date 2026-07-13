from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models import CompanyUser, Company, Terminal, TruckingCompany

router = APIRouter()

# --- REQUEST SCHEMAS ---

class GeofenceUpdateRequest(BaseModel):
    """Schema representing geofence and address update parameters."""
    geofence: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None

class CompanyInfoUpdateRequest(BaseModel):
    """Schema representing company profile and geofence updates."""
    name: Optional[str] = None
    use_remote_checkin: Optional[bool] = None
    geofence: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None


# --- RESPONSE SCHEMAS ---

class AddressSchema(BaseModel):
    """Schema representing structured address fields."""
    street: Optional[str] = None
    number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class GeofenceResponseData(BaseModel):
    """Metadata containing geofence coordinate maps and structural address fields."""
    geofence: Optional[Dict[str, Any]] = None
    address: AddressSchema

class GeofenceResponse(BaseModel):
    """Response containing terminal geofence and coordinate details."""
    success: bool = True
    data: GeofenceResponseData

class GeofenceUpdateResponseData(BaseModel):
    """Metadata confirming updating operation status."""
    updated: bool

class GeofenceUpdateResponse(BaseModel):
    """Response returned upon geofence update operations."""
    success: bool = True
    data: GeofenceUpdateResponseData

class CompanyInfoResponseData(BaseModel):
    """Metadata representing company registration and geolocation parameters."""
    id: str
    type: str
    name: str
    tax_id: str
    address: AddressSchema
    use_remote_checkin: Optional[bool] = None
    geofence: Optional[Dict[str, Any]] = None

class CompanyInfoResponse(BaseModel):
    """Response containing company profile details."""
    success: bool = True
    data: CompanyInfoResponseData

class CompanyInfoUpdateResponse(BaseModel):
    """Response returned upon company profile update operations."""
    success: bool = True
    message: str


# --- Endpoints de Empresa e Geofence ---

@router.get(
    "/geofence", 
    response_model=GeofenceResponse,
    summary="Get Company Geofence",
    description="Retrieves the geofence configuration and structured address for the operator's active company."
)
def get_geofence(
    current_user: CompanyUser = Depends(require_permission('geofence', 'read')),
    db: Session = Depends(get_db)
):
    """
    Fetches company geofence properties. Note that geofence is only valid/applicable for Terminal company types.
    """
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


@router.put(
    "/geofence", 
    response_model=GeofenceUpdateResponse,
    summary="Update Company Geofence",
    description="Updates terminal geofence parameters and address details."
)
def update_geofence(
    body: GeofenceUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('geofence', 'write')),
    db: Session = Depends(get_db)
):
    """
    Updates terminal geofence parameters and general company address details.
    """
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


@router.get(
    "/company/info", 
    response_model=CompanyInfoResponse,
    summary="Get Company Information",
    description="Retrieves administrative and geographic details for the operator's active company."
)
def get_company_info(
    current_user: CompanyUser = Depends(require_permission('company_information', 'read')),
    db: Session = Depends(get_db)
):
    """
    Fetches company administration profiles (includes remote check-in config for terminal companies).
    """
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


@router.put(
    "/company/info", 
    response_model=CompanyInfoUpdateResponse,
    summary="Update Company Information",
    description="Updates administrative company details, remote check-in status, geofences, and address settings."
)
def update_company_info(
    body: CompanyInfoUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('company_information', 'write')),
    db: Session = Depends(get_db)
):
    """
    Commits company administrative configurations, addresses, and geofence profiles to the database.
    """
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