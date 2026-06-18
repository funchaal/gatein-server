from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.database import get_db
from app.models import Company, User, CompanyUser
from app.core.security import verify_secret, APIKeyManager
from config import settings
import secrets


bearer_scheme = HTTPBearer()

# --- Dependency: API Key (B2B) ---

def get_company_from_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="Chave de API a ser validada"),
    db: Session = Depends(get_db)
) -> Company:
    if not x_api_key.startswith("sk_live_"):
        raise HTTPException(
            status_code=401, 
            detail={
                "code": "INVALID_API_KEY_FORMAT",
                "message": "O formato da chave é inválido.",
                "suggestion": "A chave deve iniciar com 'sk_live_'."
            }
        )

    parts = x_api_key.split("_", 3)
    if len(parts) < 4:
        raise HTTPException(
            status_code=401, 
            detail={
                "code": "INVALID_API_KEY_FORMAT",
                "message": "Estrutura da chave de API incompleta."
            }
        )

    prefix = f"{parts[0]}_{parts[1]}_{parts[2]}"
    company = db.query(Company).filter_by(api_key_prefix=prefix).first()

    if not company or not verify_secret(company.api_key_hash, x_api_key):
        raise HTTPException(
            status_code=401, 
            detail={
                "code": "INVALID_API_KEY",
                "message": "A credencial enviada não é válida.",
                "suggestion": "Gere uma nova chave através do painel da empresa."
            }
        )

    return company


# --- Dependency: Mobile JWT ---

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    x_device_id: str = Header(..., alias="X-Device-ID"),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "EXPIRED_TOKEN"})
    except JWTError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})

    if payload.get("device_id") != x_device_id:
        raise HTTPException(status_code=401, detail={"code": "DEVICE_MISMATCH"})

    user = db.query(User).filter_by(tax_id=payload.get("tax_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail={"code": "USER_NOT_FOUND"})

    return user


# --- Dependency: Web JWT (CompanyUser) ---

def get_current_company_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    x_device_id: str | None = Header(default=None, alias="X-Device-ID"),
    db: Session = Depends(get_db)
) -> CompanyUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "EXPIRED_TOKEN"})
    except JWTError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})

    # Device binding é opcional no web
    if payload.get("device_id"):
        if not x_device_id or payload["device_id"] != x_device_id:
            raise HTTPException(status_code=401, detail={"code": "DEVICE_MISMATCH"})

    user = db.query(CompanyUser).get(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail={"code": "USER_NOT_FOUND"})

    return user

# --- Dependency: Admin Check (composta com a anterior) ---

def get_current_admin_company_user(
    current_user: CompanyUser = Depends(get_current_company_user),
) -> CompanyUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    return current_user

def get_current_super_admin(
    # FastAPI vai procurar um header chamado 'X-Super-Admin-Token' na requisição
    x_super_admin_token: str = Header(None, description="Token secreto do Super Admin")
):
    # Pega o segredo real das variáveis de ambiente do seu servidor (.env)
    # NUNCA deixe essa string chumbada no código!
    REAL_SECRET = settings.SUPER_ADMIN_SECRET

    if not x_super_admin_token:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Header X-Super-Admin-Token ausente."}
        )

    # secrets.compare_digest é crucial! Ele evita que hackers descubram a senha 
    # medindo os milissegundos que a função demora para rejeitar uma senha errada.
    if not secrets.compare_digest(x_super_admin_token, REAL_SECRET):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Acesso negado. Token de Super Admin inválido."}
        )
    
    # Se passou, retorna True ou um objeto fictício de Admin
    return True

def require_permission(module: str, action: str = 'write'):
    """
    Uso:
        Depends(require_permission('geofence', 'read'))
        Depends(require_permission('trip_layouts'))          # write por padrão
    """
    def dependency(
        current_user: CompanyUser = Depends(get_current_company_user),
    ) -> CompanyUser:
        if not current_user.can(module, action):
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "data": { "module": module, "action": action }}
            )
        return current_user
    return dependency