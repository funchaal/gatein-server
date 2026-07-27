from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_current_admin_company_user, get_company_from_api_key
from app.core.security import APIKeyManager, verify_secret
from app.models import CompanyUser, Company

router = APIRouter()

# --- SCHEMAS ---

class APIKeyItem(BaseModel):
    prefix: str

class APIKeyListResponseData(BaseModel):
    keys: List[APIKeyItem]
    total_keys: int
    can_create: bool

class APIKeyListResponse(BaseModel):
    success: bool = True
    data: APIKeyListResponseData

class APIKeyGenerateResponseData(BaseModel):
    api_key: str
    prefix: str
    created_at: str
    message: str

class APIKeyGenerateResponse(BaseModel):
    success: bool = True
    data: APIKeyGenerateResponseData

class APIKeyRegenerateRequest(BaseModel):
    prefix: str = Field(..., description="Prefixo da chave a ser regerada")

class APIKeyValidateResponseData(BaseModel):
    """Schema representing API key validation metadata properties of a company."""
    type: str
    username: str
    name: str
    tax_id: str

class APIKeyValidateResponse(BaseModel):
    """Response containing API key validation information."""
    success: bool = True
    data: APIKeyValidateResponseData

class StandardResponse(BaseModel):
    success: bool = True
    message: str


# --- ROTAS ---

@router.get(
    "/list",
    response_model=APIKeyListResponse,
    summary="List API Keys",
    description="Lists active API key prefixes for the company."
)
def list_api_keys(
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    """
    Retorna os prefixos das chaves de API ativas para a empresa do usuário.
    """
    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COMPANY_NOT_FOUND",
                "message": "A empresa vinculada a este usuário não foi encontrada."
            }
        )

    keys: List[APIKeyItem] = []
    if company.api_key_prefix:
        keys.append(APIKeyItem(prefix=company.api_key_prefix))
    if company.api_key_secondary_prefix:
        keys.append(APIKeyItem(prefix=company.api_key_secondary_prefix))

    total_keys = len(keys)
    return {
        "success": True,
        "data": {
            "keys": keys,
            "total_keys": total_keys,
            "can_create": total_keys < 2
        }
    }


@router.post(
    "/generate", 
    response_model=APIKeyGenerateResponse,
    summary="Generate API Key",
    description="Generates a new secure API Key up to a limit of 2 active keys per company."
)
def generate_api_key(
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new key pair if limit (2) has not been reached. Returns plaintext key.
    """
    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "COMPANY_NOT_FOUND",
                "message": "A empresa vinculada a este usuário não foi encontrada."
            }
        )

    # Verificar limite de 2 chaves
    has_primary = bool(company.api_key_hash)
    has_secondary = bool(company.api_key_secondary_hash)

    if has_primary and has_secondary:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "API_KEY_LIMIT_REACHED",
                "message": "Limite de chaves de API atingido. É permitido ter no máximo 2 chaves ativas simultaneamente."
            }
        )

    try:
        full_key, prefix, key_hash = APIKeyManager.generate_key_pair()

        if not has_primary:
            company.api_key_prefix = prefix
            company.api_key_hash = key_hash
        else:
            company.api_key_secondary_prefix = prefix
            company.api_key_secondary_hash = key_hash

        db.commit()

        return {
            "success": True,
            "data": {
                "api_key": full_key,
                "prefix": prefix,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "message": "Nova chave de API gerada com sucesso. Guarde-a com segurança, ela não poderá ser recuperada posteriormente!"
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={
                "code": "API_KEY_GENERATION_FAILED", 
                "message": "Erro ao salvar a nova chave de API.",
                "error_details": str(e)
            }
        )


@router.post(
    "/regenerate",
    response_model=APIKeyGenerateResponse,
    summary="Regenerate Specific API Key",
    description="Regenerates an existing API Key identified by its prefix."
)
def regenerate_api_key(
    body: APIKeyRegenerateRequest,
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    """
    Regenerates a key pair for a given prefix, returning the new plaintext key.
    """
    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COMPANY_NOT_FOUND",
                "message": "A empresa vinculada a este usuário não foi encontrada."
            }
        )

    prefix_target = body.prefix
    is_primary = (company.api_key_prefix == prefix_target)
    is_secondary = (company.api_key_secondary_prefix == prefix_target)

    if not is_primary and not is_secondary:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "API_KEY_NOT_FOUND",
                "message": "Chave de API não encontrada para este identificador."
            }
        )

    try:
        full_key, new_prefix, new_hash = APIKeyManager.generate_key_pair()

        if is_primary:
            company.api_key_prefix = new_prefix
            company.api_key_hash = new_hash
        else:
            company.api_key_secondary_prefix = new_prefix
            company.api_key_secondary_hash = new_hash

        db.commit()

        return {
            "success": True,
            "data": {
                "api_key": full_key,
                "prefix": new_prefix,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "message": "Chave de API regerada com sucesso. Guarde a nova chave com segurança!"
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "API_KEY_REGENERATION_FAILED",
                "message": "Erro ao regerar chave de API.",
                "error_details": str(e)
            }
        )


@router.delete(
    "/{prefix}",
    response_model=StandardResponse,
    summary="Delete API Key",
    description="Deletes an API Key by prefix. If primary key is deleted and secondary exists, secondary is promoted to primary."
)
def delete_api_key(
    prefix: str = Path(..., description="Prefixo da chave a ser excluída"),
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    """
    Exclui a chave de API identificada pelo prefixo. Se a primária for excluída e existir secundária, a secundária é promovida a primária.
    """
    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COMPANY_NOT_FOUND",
                "message": "A empresa vinculada a este usuário não foi encontrada."
            }
        )

    if company.api_key_prefix == prefix:
        # Excluir a chave primária
        if company.api_key_secondary_hash:
            # Promover a secundária para primária
            company.api_key_hash = company.api_key_secondary_hash
            company.api_key_prefix = company.api_key_secondary_prefix
            company.api_key_secondary_hash = None
            company.api_key_secondary_prefix = None
        else:
            # Limpar primária
            company.api_key_hash = None
            company.api_key_prefix = None
    elif company.api_key_secondary_prefix == prefix:
        # Excluir a chave secundária
        company.api_key_secondary_hash = None
        company.api_key_secondary_prefix = None
    else:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "API_KEY_NOT_FOUND",
                "message": "Chave de API não encontrada para este identificador."
            }
        )

    try:
        db.commit()
        return {
            "success": True,
            "message": "Chave de API excluída com sucesso."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "API_KEY_DELETE_FAILED",
                "message": "Erro ao excluir chave de API.",
                "error_details": str(e)
            }
        )


@router.get(
    "/validate", 
    response_model=APIKeyValidateResponse,
    summary="Validate API Key",
    description="Validates an incoming API Key, returning company profile details associated with the key."
)
def validate_api_key_endpoint(company: Company = Depends(get_company_from_api_key)):
    """
    Validates API key authenticity and returns associated metadata details.
    """
    return {
        "success": True,
        "data": {
            "type": company.type,
            "username": company.username,
            "name": company.name,
            "tax_id": company.tax_id
        }
    }