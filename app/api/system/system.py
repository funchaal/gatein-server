import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Literal

from app.core.database import get_db
from app.core.security import hash_secret, APIKeyManager
from app.core.dependencies import get_current_super_admin
from app.models import Terminal, TruckingCompany, CompanyUser, AllowedDomain
from typing import Optional
# Supondo que você use pydantic-settings ou similar para carregar o .env
from config import settings 
from app.tools import extract_domain

router = APIRouter(tags=["System Root"])


# --- SCHEMAS ---
class AdminUserCreate(BaseModel):
    name: str = Field(..., description="Nome do usuário administrador")
    username: str = Field(..., description="Login de acesso web (ex: admin.porto)")
    password: str = Field(..., description="Senha de acesso web")

class SystemCompanyCreate(BaseModel):
    type: Literal["terminal", "trucking_company"] = Field(..., description="Tipo de empresa")
    company_username: str = Field(..., description="Identificador único da empresa (ex: porto_sul)")
    name: str = Field(..., description="Razão Social ou Nome Fantasia")
    tax_id: str = Field(..., description="CNPJ")
    phone: str
    email: EmailStr
    admin_user: AdminUserCreate

# --- ROTAS ---
@router.post("/companies", status_code=201)
def bootstrap_company(
    body: SystemCompanyCreate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)):

    # 1. Verifica se a empresa já existe (tax_id ou username)
    from app.models import Company
    if db.query(Company).filter((Company.tax_id == body.tax_id) | (Company.username == body.company_username)).first():
        raise HTTPException(status_code=409, detail={"code": "COMPANY_EXISTS", "message": "CNPJ ou Username da empresa já cadastrado."})

    # 2. Verifica se o username do admin já existe
    if db.query(CompanyUser).filter_by(username=body.admin_user.username).first():
        raise HTTPException(status_code=409, detail={"code": "USER_EXISTS", "message": "O username do administrador já está em uso."})

    try:
        # 3. Gera a API Key inicial (obrigatório pelo schema do banco)
        full_key, prefix, key_hash = APIKeyManager.generate_key_pair()

        # 4. Instancia o modelo correto baseado no tipo (Polimorfismo)
        CompanyModel = Terminal if body.type == "terminal" else TruckingCompany
        
        new_company = CompanyModel(
            username=body.company_username,
            name=body.name,
            tax_id=body.tax_id,
            phone=body.phone,
            email=body.email,
            api_key_hash=key_hash,
            api_key_prefix=prefix
        )
        db.add(new_company)
        db.flush() # Gera o ID da empresa para usar no CompanyUser

        # 5. Cria o usuário administrador vinculado à empresa
        new_admin = CompanyUser(
            company_id=new_company.id,
            username=body.admin_user.username,
            name=body.admin_user.name,
            password_hash=hash_secret(body.admin_user.password),
            is_admin=True,
            permissions={
                'geofence': 'read/write',
                'appointment_schemas': 'read/write',
                'company_information': 'read/write',
                'trip_schemas': 'read/write'
            }
        )
        db.add(new_admin)
        db.commit()

        # 6. Retorna os dados necessários para você entregar ao cliente
        return {
            "success": True,
            "data": {
                "company_id": str(new_company.id),
                "type": new_company.type,
                "name": new_company.name,
                "admin_username": new_admin.username,
                "initial_api_key": full_key, # Exiba apenas nesta resposta!
                "message": "Empresa e administrador criados com sucesso."
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})
    

class AllowedDomainCreate(BaseModel):
    # Pedimos a URL completa para validar se é um link real, 
    # mas no backend vamos extrair apenas o domínio.
    url: HttpUrl 
    is_active: Optional[bool] = True

class CompanyUserPasswordUpdate(BaseModel):
    password: str = Field(..., description="Nova senha de acesso do usuário da empresa")


@router.post("/allowed-domains")
def create_allowed_domain(
    payload: AllowedDomainCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_super_admin) # IMPORTANTE: Proteger a rota!
):
    # 1. Limpa a URL e extrai o domínio raiz
    clean_domain = extract_domain(payload.url)
    
    # 2. Verifica se o domínio já existe na tabela para evitar duplicidade
    existing_domain = db.query(AllowedDomain).filter(
        AllowedDomain.domain == clean_domain
    ).first()
    
    if existing_domain:
        # Se já existe, apenas garante que está ativo
        if not existing_domain.is_active:
            existing_domain.is_active = True
            db.commit()
            return {
                "success": True,
                "message": "Domínio reativado com sucesso",
                "data": {
                    "domain": clean_domain
                }
            }
            
        raise HTTPException(
            status_code=400, 
            detail={"code": "DOMAIN_EXISTS", "message": f"O domínio '{clean_domain}' já está cadastrado e ativo."}
        )

    # 3. Cria o novo registro no banco
    new_allowed_domain = AllowedDomain(
        domain=clean_domain,
        is_active=payload.is_active
    )
    
    db.add(new_allowed_domain)
    db.commit()
    db.refresh(new_allowed_domain)
    
    return {
        "success": True,
        "message": "Domínio validado e cadastrado com sucesso",
        "data": {
            "id": new_allowed_domain.id,
            "domain": new_allowed_domain.domain,
            "is_active": new_allowed_domain.is_active
        }
    }

@router.delete("/allowed-domains/{domain_id}")
def deactivate_allowed_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_super_admin)
):
    domain_obj = db.query(AllowedDomain).filter(AllowedDomain.id == domain_id).first()
    
    if not domain_obj:
        raise HTTPException(
            status_code=404, 
            detail={"code": "NOT_FOUND", "message": "Domínio não encontrado."}
        )
        
    domain_obj.is_active = False
    
    # Desativa também todos os serviços relacionados a este domínio
    from app.models import CompanyService
    db.query(CompanyService).filter(CompanyService.domain_id == domain_id).update(
        {"is_active": False}, synchronize_session=False
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": "Domínio desativado com sucesso",
        "data": {
            "id": domain_obj.id,
            "domain": domain_obj.domain,
            "is_active": domain_obj.is_active
        }
    }


@router.put("/company-users/{user_id}/password", status_code=200)
def update_company_user_password(
    user_id: uuid.UUID,
    body: CompanyUserPasswordUpdate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(get_current_super_admin)
):
    # 1. Busca o usuário da empresa
    user = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "Usuário não encontrado."}
        )

    try:
        # 2. Atualiza a senha
        user.password_hash = hash_secret(body.password)
        db.commit()
        return {
            "success": True,
            "message": "Senha do usuário da empresa atualizada com sucesso."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )