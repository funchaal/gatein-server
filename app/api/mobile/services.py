import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import generate_jwt
from app.models import User, CompanyService

router = APIRouter()

# --- SCHEMAS ---

class AuthTokenResponseData(BaseModel):
    token: str
    expires_in: int

class AuthTokenResponse(BaseModel):
    success: bool = True
    data: AuthTokenResponseData

class ServiceResponseData(BaseModel):
    id: str
    company_id: str
    title: str
    description: Optional[str]
    url: str
    icon_url: Optional[str]
    is_active: bool
    created_at: Optional[str] = None

class ServiceListResponse(BaseModel):
    success: bool = True
    data: List[ServiceResponseData]

class ServiceIdsRequest(BaseModel):
    ids: List[uuid.UUID]


# --- ROTAS ---

@router.get("/companies/{company_id}/services", response_model=ServiceListResponse)
def get_services_by_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    services = db.query(CompanyService).filter_by(company_id=company_id, is_active=True).all()
    return {"success": True, "data": [
        {
            "id": str(s.id),
            "company_id": str(s.company_id),
            "title": s.title,
            "description": s.description,
            "url": s.url,
            "icon_url": s.icon_url,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        }
        for s in services
    ]}

@router.post("/services/by-ids", response_model=ServiceListResponse)
def get_services_by_ids(
    body: ServiceIdsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    services = db.query(CompanyService).filter(CompanyService.id.in_(body.ids)).all()
    return {"success": True, "data": [
        {
            "id": str(s.id),
            "company_id": str(s.company_id),
            "title": s.title,
            "description": s.description,
            "url": s.url,
            "icon_url": s.icon_url,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        }
        for s in services
    ]}

@router.get("/auth-token", response_model=AuthTokenResponse)
def generate_integration_auth_token(
    current_user: User = Depends(get_current_user)
):
    token = generate_jwt(
        payload={"user_id": str(current_user.id)},
        exp_delta=timedelta(minutes=3)
    )
    return {
        "success": True,
        "data": {
            "token": token,
            "expires_in": 180
        }
    }
