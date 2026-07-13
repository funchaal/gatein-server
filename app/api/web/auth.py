from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.database import get_db
from app.core.security import verify_secret, generate_jwt, hash_secret
from app.core.dependencies import get_current_company_user
from app.models import CompanyUser
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