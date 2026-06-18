from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_admin_company_user, get_company_from_api_key
from app.core.security import APIKeyManager, verify_secret
from app.models import CompanyUser, Company

router = APIRouter()

# --- SCHEMAS ---

class APIKeyGenerateResponseData(BaseModel):
    api_key: str
    created_at: str
    message: str

class APIKeyGenerateResponse(BaseModel):
    success: bool = True
    data: APIKeyGenerateResponseData

class APIKeyValidateResponseData(BaseModel):
    valid: bool
    company_id: str
    username: str
    type: str

class APIKeyValidateResponse(BaseModel):
    success: bool = True
    data: APIKeyValidateResponseData


# --- ROTAS ---

@router.post("/generate", response_model=APIKeyGenerateResponse)
def generate_api_key(
    current_user: CompanyUser = Depends(get_current_admin_company_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).get(current_user.company_id)
    if not company:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "COMPANY_NOT_FOUND",
                "message": "A empresa vinculada a este usuário não foi encontrada.",
                "suggestion": "Verifique a integridade dos dados do usuário logado."
            }
        )

    try:
        full_key, prefix, key_hash = APIKeyManager.generate_key_pair()
        company.api_key_prefix = prefix
        company.api_key_hash = key_hash
        db.commit()

        return {
            "success": True,
            "data": {
                "api_key": full_key,
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
    

@router.get("/validate")
def validate_api_key_endpoint(company: Company = Depends(get_company_from_api_key)):
    return {
        "success": True,
        "data": {
            "type": company.type,
            "username": company.username,
            "name": company.name,
            "tax_id": company.tax_id
        }
    }