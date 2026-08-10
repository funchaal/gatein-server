import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.database import get_db
from app.core.dependencies import get_current_admin_company_user, get_current_company_user, require_permission
from app.core.sqids import encode_id, decode_id
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
    service_ids: List[str]
    is_active: bool

class ServiceBatchDeleteRequest(BaseModel):
    service_ids: List[str]

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
    """Response containing details of a single company service."""
    success: bool = True
    data: ServiceResponseData
    message: Optional[str] = None

class ServiceBatchStatusResponseData(BaseModel):
    """Metadata detailing status updating status and updated service IDs."""
    status: str
    ids: List[str]

class ServiceBatchStatusResponse(BaseModel):
    """Response returned upon batch service status update operation."""
    success: bool = True
    data: ServiceBatchStatusResponseData
    message: Optional[str] = None

class ServiceBatchDeleteResponseData(BaseModel):
    """Metadata containing status details and deleted service IDs."""
    status: str
    ids: List[str]

class ServiceBatchDeleteResponse(BaseModel):
    """Response returned upon batch service deletion operation."""
    success: bool = True
    data: ServiceBatchDeleteResponseData


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
            "id": encode_id(s.id),
            "company_id": encode_id(s.company_id),
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

    # ETAPA IGNORADA TEMPORARIAMENTE (CÓDIGO ORIGINAL MANTIDO COMENTADO):
    # if not allowed_domain:
    #     raise HTTPException(
    #         status_code=400,
    #         detail={"code": "DOMAIN_NOT_ALLOWED", "message": "O domínio não está cadastrado. Entre em contato com o suporte."}
    #     )

    # Se o domínio não estiver cadastrado, cria automaticamente para satisfazer a FK domain_id
    if not allowed_domain:
        allowed_domain = AllowedDomain(domain=domain, is_active=True)
        db.add(allowed_domain)
        db.flush()

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
                "id": encode_id(new_service.id),
                "company_id": encode_id(new_service.company_id),
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
    service_id: str,
    body: ServiceUpdateRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    try:
        decoded_id = decode_id(service_id)
    except (ValueError, Exception):
        raise HTTPException(status_code=400, detail="ID de serviço inválido.")

    target = db.query(CompanyService).filter_by(id=decoded_id, company_id=current_user.company_id).first()
    if not target:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Serviço não encontrado."}
        )

    message = None
    if body.url is not None:
        domain = extract_domain(body.url)
        allowed_domain = db.query(AllowedDomain).filter_by(domain=domain).first()

        # ETAPA IGNORADA TEMPORARIAMENTE (CÓDIGO ORIGINAL MANTIDO COMENTADO):
        # if not allowed_domain:
        #     raise HTTPException(
        #         status_code=400,
        #         detail={"code": "DOMAIN_NOT_ALLOWED", "message": "O domínio não está cadastrado. Entre em contato com o suporte."}
        #     )

        # Se o domínio não estiver cadastrado, cria automaticamente para satisfazer a FK domain_id
        if not allowed_domain:
            allowed_domain = AllowedDomain(domain=domain, is_active=True)
            db.add(allowed_domain)
            db.flush()

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
                "id": encode_id(target.id),
                "company_id": encode_id(target.company_id),
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

@router.patch(
    "/services/status", 
    response_model=ServiceBatchStatusResponse,
    summary="Update Services Activation Status",
    description="Bulk updates activation flags for a list of service IDs, ensuring they belong to the user's company."
)
def update_services_status(
    body: ServiceBatchStatusRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    """
    Updates is_active properties of requested company services. Validates domain permissions.
    """
    decoded_ids = []
    for sid in body.service_ids:
        try:
            decoded_ids.append(decode_id(sid))
        except (ValueError, Exception):
            pass

    targets = db.query(CompanyService).filter(
        CompanyService.id.in_(decoded_ids),
        CompanyService.company_id == current_user.company_id
    ).all()
    
    if not targets:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Nenhum serviço encontrado."}
        )
        
    messages = []
    updated_ids = []
    
    # Batch query allowed domains to avoid database query inside loop
    domain_ids = {t.domain_id for t in targets if t.domain_id}
    allowed_domains_map = {}
    if domain_ids:
        allowed_domains = db.query(AllowedDomain).filter(AllowedDomain.id.in_(domain_ids)).all()
        allowed_domains_map = {ad.id: ad for ad in allowed_domains}
    
    try:
        for target in targets:
            allowed_domain = allowed_domains_map.get(target.domain_id)
            if allowed_domain and body.is_active and not allowed_domain.is_active:
                messages.append(f"Serviço '{target.title}' não pode ser ativado pois o domínio associado está desativado.")
                target.is_active = False
            else:
                target.is_active = body.is_active
            updated_ids.append(encode_id(target.id))

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


@router.delete(
    "/services", 
    response_model=ServiceBatchDeleteResponse,
    summary="Delete Services",
    description="Bulk deletes services matching provided IDs list."
)
def delete_services(
    body: ServiceBatchDeleteRequest,
    current_user: CompanyUser = Depends(require_permission('services', 'write')),
    db: Session = Depends(get_db)
):
    """
    Deletes multiple company services in bulk.
    """
    if not current_user.can("services", "write"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})

    decoded_ids = []
    for sid in body.service_ids:
        try:
            decoded_ids.append(decode_id(sid))
        except (ValueError, Exception):
            pass

    targets = db.query(CompanyService).filter(
        CompanyService.id.in_(decoded_ids),
        CompanyService.company_id == current_user.company_id
    ).all()
    
    if not targets:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Nenhum serviço encontrado."}
        )

    try:
        deleted_ids = [encode_id(t.id) for t in targets]
        for target in targets:
            target.is_active = False
        db.commit()
        return {"success": True, "data": {"status": "deleted", "ids": deleted_ids}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )