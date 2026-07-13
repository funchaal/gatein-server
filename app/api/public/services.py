from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.database import get_db
from app.models import Company, User
from config import settings
from app.core.dependencies import get_company_from_api_key

router = APIRouter()

# --- SCHEMAS ---

class UserIntegrationResponseData(BaseModel):
    """Schema representing the validated user information data."""
    tax_id: str
    name: str | None
    phone: str | None
    email: str | None = None

class UserIntegrationResponse(BaseModel):
    """Schema representing the validated user response structure."""
    success: bool = True
    data: UserIntegrationResponseData


# --- ROTAS ---

@router.get(
    "/services/validate-user-token",
    response_model=UserIntegrationResponse,
    summary="Validate User Service Token",
    description=(
        "Decodes and validates a short-lived JWT auth token injected by the GateIn mobile app into a "
        "company service page. Returns user identity details (tax_id, name, phone, email) if the token "
        "is valid, not expired, and the user is registered."
    )
)
def validate_user_token(
    auth_token: str = Header(..., alias="Auth-Token"),
    company: Company = Depends(get_company_from_api_key),
    db: Session = Depends(get_db)
):
    """
    Validates a JWT token provided via the 'Auth-Token' header.
    Requires authentication via API Key.
    """
    try:
        payload = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401, 
            detail={"code": "EXPIRED_TOKEN", "message": "O token expirou."}
        )
    except JWTError:
        raise HTTPException(
            status_code=401, 
            detail={"code": "INVALID_TOKEN", "message": "O token é inválido."}
        )

    user = db.query(User).filter_by(id=payload.get("user_id")).first()
    if not user:
        raise HTTPException(
            status_code=401, 
            detail={"code": "USER_NOT_FOUND", "message": "Usuário não encontrado."}
        )

    return {
        "success": True,
        "data": {
            "tax_id": user.tax_id,
            "name": user.name,
            "phone": user.phone,
            "email": getattr(user, "email", None)
        }
    }
