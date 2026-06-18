from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.database import get_db
from app.models import Company, User
from config import settings
from app.core.dependencies import get_company_from_api_key
from app.api.web.apiKey import validate_api_key_endpoint


router = APIRouter()
bearer_scheme = HTTPBearer()

class UserIntegrationResponseData(BaseModel):
    tax_id: str
    name: str | None
    phone: str | None
    email: str | None = None

class UserIntegrationResponse(BaseModel):
    success: bool = True
    data: UserIntegrationResponseData


@router.get("/validate-user", response_model=UserIntegrationResponse)
def validate_user_token(
    auth_token: str = Header(..., alias="Auth-Token"),
    company: Company = Depends(get_company_from_api_key),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "EXPIRED_TOKEN", "message": "O token expirou."})
    except JWTError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "O token é inválido."})

    user = db.query(User).filter_by(id=payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail={"code": "USER_NOT_FOUND", "message": "Usuário não encontrado."})

    return {
        "success": True,
        "data": {
            "tax_id": user.tax_id,
            "name": user.name,
            "phone": user.phone,
            "email": getattr(user, "email", None)
        }
    }


router.add_api_route(
    "/validate-api-key", 
    endpoint=validate_api_key_endpoint, 
    methods=["GET"]
)