from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_secret, generate_jwt, hash_secret
from app.core.dependencies import get_current_company_user
from app.models import CompanyUser
from app.schemas.auth import WebLoginRequest, WebDevResetPasswordRequest
from config import settings

router = APIRouter()

@router.post("/login")
def login(body: WebLoginRequest, db: Session = Depends(get_db)):
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


@router.post("/session/restore")
def restore_session(current_user: CompanyUser = Depends(get_current_company_user)):
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


@router.post("/dev/reset-password")
def dev_reset_password(body: WebDevResetPasswordRequest, db: Session = Depends(get_db)):
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