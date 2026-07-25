from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
import secrets as secrets_module

from app.core.database import get_db
from app.core.security import verify_secret, generate_jwt, hash_secret
from app.core.dependencies import get_current_company_user, get_current_admin_company_user
from app.models import CompanyUser, StagingPassword
from app.schemas.auth import WebLoginRequest, WebDevResetPasswordRequest
from config import settings


router = APIRouter()

# --- RESPONSE SCHEMAS ---

class WebUserSchema(BaseModel):
    """Schema representing the logged-in web user's profile details."""
    name: str
    username: str
    permissions: Dict[str, Any]
    is_admin: bool
    company_id: str
    company_type: str

class WebLoginResponseData(BaseModel):
    """Wrapped data holding authentication token and user profile details."""
    token: str
    user: WebUserSchema

class WebLoginResponse(BaseModel):
    """Response returned upon successful web login authentication."""
    success: bool = True
    data: WebLoginResponseData

class WebSessionRestoreResponseData(BaseModel):
    """Wrapped user profile details for session restoration."""
    user: WebUserSchema

class WebSessionRestoreResponse(BaseModel):
    """Response returned upon successful session restoration."""
    success: bool = True
    data: WebSessionRestoreResponseData

class SimpleSuccessResponse(BaseModel):
    """Standard success schema containing status flags and message parameters."""
    success: bool = True
    message: Optional[str] = None


# --- ROTAS ---

@router.post(
    "/login", 
    response_model=WebLoginResponse,
    summary="Web operator Login",
    description="Authenticates a company user/operator and issues a session JWT token."
)
def login(body: WebLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates web operator user using username and password. Returns JWT token and user profile.
    """
    user = db.query(CompanyUser).filter_by(username=body.username).first()
    
    if not user or not verify_secret(user.password_hash, body.password):
        raise HTTPException(
            status_code=401, 
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Usuário ou senha incorretos."
            }
        )

    payload = {"sub": str(user.id), "company_id": str(user.company_id)}
    if hasattr(body, 'device') and body.device:
        payload["device_id"] = body.device

    token = generate_jwt(payload, exp_delta=settings.JWT_EXPIRATION_DELTA_WEB)
    
    return {
        "success": True, 
        "data": {
            "token": token,
            "user": {
                "name": user.name,
                "username": user.username,
                "permissions": user.permissions,
                "is_admin": user.is_admin,
                "company_id": str(user.company_id), 
                "company_type": user.company.type
            }
        }
    }


@router.post(
    "/session/restore", 
    response_model=WebSessionRestoreResponse,
    summary="Restore Web Session",
    description="Validates active web operator credentials to restore the dashboard session."
)
def restore_session(current_user: CompanyUser = Depends(get_current_company_user)):
    """
    Restores user session profile from active JWT session metadata.
    """
    return {
        "success": True, 
        "data": {
            "user": {
                "name": current_user.name,
                "username": current_user.username,
                "permissions": current_user.permissions,
                "is_admin": current_user.is_admin,
                "company_id": str(current_user.company_id), 
                "company_type": current_user.company.type
            }
        }
    }


@router.post(
    "/dev/reset-password", 
    response_model=SimpleSuccessResponse,
    summary="Dev Reset Password Tool",
    description="Resets operator passwords. Safety lock: Enabled ONLY in dev environment configuration."
)
def dev_reset_password(body: WebDevResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Resets passwords directly on target username if local settings configuration allows dev access.
    """
    # TRAVA DE SEGURANÇA: Impede execução em produção
    if getattr(settings, "ENVIRONMENT", "prod") != "dev":
        raise HTTPException(
            status_code=403, 
            detail={
                "code": "FORBIDDEN",
                "message": "Esta rota está disponível apenas no ambiente de desenvolvimento."
            }
        )

    user = db.query(CompanyUser).filter_by(username=body.username).first()
    if not user:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "USER_NOT_FOUND",
                "message": "Usuário não encontrado."
            }
        )

    user.password_hash = hash_secret(body.new_password)
    db.commit()

    return {"success": True, "message": "Senha alterada com sucesso."}


# ─── STAGING: Geração de Senha Mestra ────────────────────────────────────────

class StagingPasswordResponse(BaseModel):
    """Resposta com a senha mestra gerada (exibida apenas uma vez)."""
    success: bool = True
    data: Dict[str, Any]


@router.post(
    "/staging/password/generate",
    response_model=StagingPasswordResponse,
    summary="Gerar Senha Mestra de Homologação",
    description=(
        "Gera (ou regenera) a senha mestra de homologação para a empresa do usuário logado. "
        "A senha é retornada em texto plano APENAS nesta resposta — não é armazenada em texto. "
        "Disponível SOMENTE em ambiente de homologação (PROD=False) e requer perfil de admin. "
        "Ao gerar uma nova senha, a anterior é automaticamente revogada."
    )
)
def generate_staging_password(
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_admin_company_user)
):
    """
    Gera uma senha mestra criptograficamente segura vinculada à empresa.
    Faz upsert: se já existir, substitui a anterior.
    """
    if settings.IS_PROD:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Esta funcionalidade só está disponível no ambiente de homologação (PROD=False)."
            }
        )

    # Gera senha forte: UUID + token seguro = difícil de reproduzir por força bruta
    raw_password = secrets_module.token_urlsafe(32)
    password_hash = hash_secret(raw_password)

    # Upsert: uma empresa só pode ter uma staging password ativa
    existing = db.query(StagingPassword).filter_by(
        company_id=current_user.company_id
    ).first()

    if existing:
        existing.password_hash = password_hash
    else:
        new_record = StagingPassword(
            company_id=current_user.company_id,
            password_hash=password_hash
        )
        db.add(new_record)

    db.commit()

    return {
        "success": True,
        "data": {
            "staging_password": raw_password,
            "message": (
                "Guarde esta senha com segurança. "
                "Ela não poderá ser recuperada — apenas regerada, o que revogará a atual."
            ),
            "company_id": str(current_user.company_id)
        }
    }


@router.get(
    "/staging/password/status",
    summary="Status da Senha Mestra de Homologação",
    description=(
        "Verifica se a empresa já possui uma senha mestra de homologação ativa. "
        "Não retorna a senha — apenas informa se existe e quando foi gerada. "
        "Disponível SOMENTE em ambiente de homologação (PROD=False)."
    )
)
def get_staging_password_status(
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_admin_company_user)
):
    """
    Retorna o status da senha mestra de staging para a empresa logada.
    """
    if settings.IS_PROD:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Esta funcionalidade só está disponível no ambiente de homologação (PROD=False)."
            }
        )

    existing = db.query(StagingPassword).filter_by(
        company_id=current_user.company_id
    ).first()

    return {
        "success": True,
        "data": {
            "has_password": existing is not None,
            "generated_at": existing.created_at.isoformat() if existing else None,
            "updated_at": existing.updated_at.isoformat() if existing else None,
        }
    }