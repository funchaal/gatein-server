from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import json
import random
from typing import Optional
import datetime

from app.core.database import get_db
from app.core.redis import redis_client
from app.core.security import generate_jwt, verify_secret, hash_secret
from app.core.dependencies import get_current_user
from app.models import User, Driver
from app.schemas.auth import (
    VerifyCurrentPasswordRequest, ForgotPasswordRequest,
    ValidateForgotCodeRequest, ChangePasswordRequest
)
from config import settings
from jose import jwt, JWTError

router = APIRouter()

@router.post("/reset/verify")
def verify_password_logged_in(
    body: VerifyCurrentPasswordRequest,
    current_user: User = Depends(get_current_user)
):
    if not verify_secret(current_user.password_hash, body.current_password):
        raise HTTPException(status_code=401, detail={"code": "CURRENT_PASSWORD_INVALID"})

    hash_tail = current_user.password_hash[-10:] if current_user.password_hash else ""
    
    token_payload = {
        "sub": str(current_user.id),
        "hash_tail": hash_tail,
        "type": "pwd_recovery"
    }
    
    exp_delta = datetime.timedelta(minutes=10)
    token = generate_jwt(token_payload, exp_delta=exp_delta)
    
    return {"success": True, "data": {"token": token}}

@router.post("/forgot")
def forgot_password_request(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(tax_id=body.tax_id).first()
    if not driver or driver.driver_license_number != body.driver_license:
        raise HTTPException(status_code=400, detail={"code": "DRIVER_LICENSE_INVALID"})
    
    user = db.query(User).filter_by(tax_id=body.tax_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})

    code = random.randint(100000, 999999)
    redis_key = f"pwd_recovery:{body.tax_id}"
    
    redis_data = {
        "code": code,
        "device": body.device,
        "attempts": 0
    }
    redis_client.setex(redis_key, 600, json.dumps(redis_data))
    
    print(f"DEBUG RECOVERY CODE {body.tax_id}: {code}")
    
    phone = user.phone or ""
    censored_phone = f"{phone[:3]}***{phone[-2:]}" if len(phone) >= 5 else "***"

    return {"success": True, "data": { "phone": censored_phone } }

@router.post("/validate-code")
def validate_forgot_code(body: ValidateForgotCodeRequest, db: Session = Depends(get_db)):
    redis_key = f"pwd_recovery:{body.tax_id}"
    stored = redis_client.get(redis_key)
    
    if not stored:
        raise HTTPException(status_code=400, detail={"code": "CODE_EXPIRED_OR_INVALID"})

    stored_json = json.loads(stored)
    
    if stored_json.get("device") != body.device:
        raise HTTPException(status_code=400, detail={"code": "DEVICE_MISMATCH"})
        
    if str(stored_json.get("code")) != body.code:
        attempts = stored_json.get("attempts", 0) + 1
        if attempts >= 3:
            redis_client.delete(redis_key)
            raise HTTPException(status_code=400, detail={"code": "TOO_MANY_ATTEMPTS"})
            
        stored_json["attempts"] = attempts
        redis_client.setex(redis_key, 600, json.dumps(stored_json))
        raise HTTPException(status_code=400, detail={"code": "INVALID_CODE"})

    redis_client.delete(redis_key)
    
    user = db.query(User).filter_by(tax_id=body.tax_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})

    hash_tail = user.password_hash[-10:] if user.password_hash else ""
    
    token_payload = {
        "sub": str(user.id),
        "hash_tail": hash_tail,
        "type": "pwd_recovery"
    }
    
    exp_delta = datetime.timedelta(minutes=10)
    token = generate_jwt(token_payload, exp_delta=exp_delta)
    
    return {"success": True, "data": {"token": token}}

@router.post("/change")
def change_password(
    body: ChangePasswordRequest,
    x_password_reset_token: Optional[str] = Header(None, alias="X-Password-Reset-Token"),
    db: Session = Depends(get_db)
):
    if not x_password_reset_token:
        raise HTTPException(status_code=401, detail={"code": "MISSING_OR_INVALID_TOKEN"})
        
    token = x_password_reset_token
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_OR_EXPIRED_TOKEN"})
        
    if payload.get("type") != "pwd_recovery":
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN_TYPE"})
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN_PAYLOAD"})
        
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
        
    hash_tail = user.password_hash[-10:] if user.password_hash else ""
    if payload.get("hash_tail") != hash_tail:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_INVALIDATED"})
        
    user.password_hash = hash_secret(body.new_password)
    db.commit()
    
    return {"success": True}
