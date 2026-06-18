import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_admin_company_user, get_current_company_user, require_permission
from app.models import CompanyUser, CompanyService, AllowedDomain
from app.tools import extract_domain

router = APIRouter()

# --- SCHEMAS ---

class ServiceCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    icon_url: Optional[str] = None
    is_active: bool = True

class ServiceUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    icon_url: Optional[str] = None

class ServiceBatchStatusRequest(BaseModel):
    service_ids: List[uuid.UUID]
    is_active: bool

class ServiceBatchDeleteRequest(BaseModel):
    service_ids: List[uuid.UUID]

class ServiceResponseData(BaseModel):
    id: str
    company_id: str
    title: str
    description: Optional[str]
    url: str
    icon_url: Optional[str]
    is_active: bool
    is_domain_active: bool
    created_at: Optional[str] = None

class ServiceListResponse(BaseModel):
    success: bool = True
    data: List[ServiceResponseData]

class ServiceSingleResponse(BaseModel):
    success: bool = True
    data: ServiceResponseData
    message: Optional[str] = None


# --- ROTAS ---

@router.get("/services", response_model=ServiceListResponse)
def get_services(
    current_user: CompanyUser = Depends(require_permission('services', 'read')),
    db: Session = Depends(get_db)
):

    results = db.query(CompanyService, AllowedDomain.is_active.label("is_domain_active"))\
        .join(AllowedDomain, CompanyService.domain_id == AllowedDomain.id)\
        .filter(CompanyService.company_id == current_user.company_id).all()
        
    return {"success": True, "data": [
        {
            "id": str(s.id),
            "company_id": str(s.company_id),
            "title": s.title,
            "description": s.description,
            "url": s.url,
            "icon_url": s.icon_url,
            "is_active": s.is_active,
            "is_domain_active": is_domain_active,
            "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        }
        for s, is_domain_active in results
    ]}

@router.post("/services", status_code=201, response_model=ServiceSingleResponse)
def create_service(
    body: ServiceCreateRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    domain = extract_domain(body.url)
    allowed_domain = db.query(AllowedDomain).filter_by(domain=domain).first()

    if not allowed_domain:
        raise HTTPException(
            status_code=400,
            detail={"code": "DOMAIN_NOT_ALLOWED", "message": "O domínio não está cadastrado. Entre em contato com o suporte."}
        )

    message = None
    if not allowed_domain.is_active:
        message = "Serviço criado, mas como o domínio está desativado, o serviço não será usável no aplicativo."

    try:
        new_service = CompanyService(
            company_id=current_user.company_id,
            title=body.title,
            description=body.description,
            domain_id=allowed_domain.id,
            url=body.url,
            icon_url=body.icon_url,
            is_active=body.is_active if allowed_domain.is_active else False
        )
        db.add(new_service)
        db.commit()
        
        response_data = {
            "success": True,
            "data": {
                "id": str(new_service.id),
                "company_id": str(new_service.company_id),
                "title": new_service.title,
                "description": new_service.description,
                "url": new_service.url,
                "icon_url": new_service.icon_url,
                "is_active": new_service.is_active,
                "is_domain_active": allowed_domain.is_active,
                "created_at": new_service.created_at.isoformat() + "Z" if new_service.created_at else None,
            }
        }
        if message:
            response_data["message"] = message
            
        return response_data
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.put("/services/{service_id}", response_model=ServiceSingleResponse)
def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    target = db.query(CompanyService).filter_by(id=service_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Serviço não encontrado."}
        )

    message = None
    if body.url is not None:
        domain = extract_domain(body.url)
        allowed_domain = db.query(AllowedDomain).filter_by(domain=domain).first()

        if not allowed_domain:
            raise HTTPException(
                status_code=400,
                detail={"code": "DOMAIN_NOT_ALLOWED", "message": "O domínio não está cadastrado. Entre em contato com o suporte."}
            )

        if not allowed_domain.is_active:
            message = "Serviço atualizado, mas como o domínio está desativado, o serviço não será usável no aplicativo."
            
        target.domain_id = allowed_domain.id
    else:
        allowed_domain = db.query(AllowedDomain).filter_by(id=target.domain_id).first()

    if not allowed_domain.is_active:
        target.is_active = False

    try:
        if body.title is not None:        target.title = body.title
        if body.description is not None:  target.description = body.description
        if body.url is not None:          target.url = body.url
        if body.icon_url is not None:     target.icon_url = body.icon_url

        db.commit()
        
        response_data = {
            "success": True,
            "data": {
                "id": str(target.id),
                "company_id": str(target.company_id),
                "title": target.title,
                "description": target.description,
                "url": target.url,
                "icon_url": target.icon_url,
                "is_active": target.is_active,
                "is_domain_active": allowed_domain.is_active,
                "created_at": target.created_at.isoformat() + "Z" if target.created_at else None,
            }
        }
        if message:
            response_data["message"] = message
            
        return response_data
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.patch("/services/status")
def update_services_status(
    body: ServiceBatchStatusRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    targets = db.query(CompanyService).filter(
        CompanyService.id.in_(body.service_ids),
        CompanyService.company_id == current_user.company_id
    ).all()
    
    if not targets:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Nenhum serviço encontrado."}
        )
        
    messages = []
    updated_ids = []
    
    try:
        for target in targets:
            allowed_domain = db.query(AllowedDomain).filter_by(id=target.domain_id).first()
            if body.is_active and not allowed_domain.is_active:
                messages.append(f"Serviço '{target.title}' não pode ser ativado pois o domínio associado está desativado.")
                target.is_active = False
            else:
                target.is_active = body.is_active
            updated_ids.append(str(target.id))

        db.commit()
        
        response_data = {"success": True, "data": {"status": "updated", "ids": updated_ids}}
        if messages:
            response_data["message"] = " ".join(messages)
            
        return response_data
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

@router.delete("/services")
def delete_services(
    body: ServiceBatchDeleteRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    if not current_user.can("services", "write"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})

    targets = db.query(CompanyService).filter(
        CompanyService.id.in_(body.service_ids),
        CompanyService.company_id == current_user.company_id
    ).all()
    
    if not targets:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Nenhum serviço encontrado."}
        )

    try:
        deleted_ids = [str(t.id) for t in targets]
        for target in targets:
            db.delete(target)
        db.commit()
        return {"success": True, "data": {"status": "deleted", "ids": deleted_ids}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )