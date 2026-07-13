from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json, random

from app.core.database import get_db
from app.core.redis import redis_client
from app.core.security import generate_jwt, verify_secret, hash_secret
from app.core.dependencies import get_current_user
from app.models import User, RegisterRequest as RegisterRequestModel, Driver
from app.schemas.auth import (
    CheckStatusRequest, OTPSendRequest, OTPVerifyRequest,
    DriverLicenseRequest, RegisterRequest, MobileLoginRequest,
    DeleteRegisterRequest, ProfilePhoneVerifyRequest,
    EmailSendRequest, EmailVerifyRequest
)
from config import settings

router = APIRouter()

# --- SCHEMAS (Pydantic Response Models) ---

class CheckStatusUserData(BaseModel):
    """Details showing the user's registration step and masked identifier name."""
    register_step: str
    masked_name: Optional[str] = None

class CheckStatusResponseData(BaseModel):
    """Wrapped data holding checking status."""
    user: CheckStatusUserData

class CheckStatusResponse(BaseModel):
    """Response containing checking status parameters."""
    success: bool = True
    data: CheckStatusResponseData

class SimpleSuccessResponse(BaseModel):
    """Standard success model containing a success flag."""
    success: bool = True

class MobileUserSchema(BaseModel):
    """Mobile user profile information."""
    tax_id: str
    name: str
    phone: str
    email: Optional[str] = None

class AuthTokenResponseData(BaseModel):
    """Wrapped authorization token and user profile details."""
    token: str
    user: MobileUserSchema

class AuthResponse(BaseModel):
    """Response returned upon successful user authentication or registration."""
    success: bool = True
    data: AuthTokenResponseData

class UserProfileResponseData(BaseModel):
    """Wrapped user profile details."""
    user: MobileUserSchema

class UserProfileResponse(BaseModel):
    """Response returned when fetching or validating active user profiles."""
    success: bool = True
    data: UserProfileResponseData


def mask_full_name(name: str) -> str:
    """
    Masks user's full name for confidentiality (e.g. 'John Doe' -> 'Joh*** Doe***').
    """
    if not name:
        return "Usuário"
    
    parts = name.strip().split()
    masked_parts = [
        f"{part[:3]}***" if len(part) > 3 else f"{part[:1]}***" 
        for part in parts
    ]
    return " ".join(masked_parts)


@router.post(
    "/check-status", 
    response_model=CheckStatusResponse,
    summary="Check Registration Status",
    description="Returns the user's current registration step (registered, new, or pending state) for onboarding validation."
)
def check_status(body: CheckStatusRequest, db: Session = Depends(get_db)):
    """
    Validates user tax_id to dictate client onboarding screens.
    """
    user = db.query(User).filter_by(tax_id=body.tax_id).first()
    if user:
        return {"success": True, "data": {"user": {"register_step": "registered"}}}

    pending = db.query(RegisterRequestModel).filter_by(tax_id=body.tax_id).first()
    if pending:
        masked = mask_full_name(pending.name)
        return {"success": True, "data": {"user": {"register_step": pending.register_step, "masked_name": masked}}}

    return {"success": True, "data": {"user": {"register_step": "new"}}}


@router.post(
    "/otp/send", 
    response_model=SimpleSuccessResponse,
    summary="Send OTP Verification Code",
    description="Generates a numeric verification OTP, saves it in Redis with a 5-minute expiration, and triggers dispatch."
)
def send_otp(body: OTPSendRequest):
    """
    Generates and registers OTP for phone validation.
    """
    code = random.randint(1000, 9999)
    redis_client.setex(f"otp:{body.tax_id}", 300, json.dumps({"code": code, "phone": body.phone}))
    print(f"DEBUG OTP {body.tax_id}: {code}")
    return {"success": True}


@router.post(
    "/otp/verify", 
    response_model=SimpleSuccessResponse,
    summary="Verify OTP Code",
    description="Validates the sent OTP code against the database. Transitions registration step to driver_license on success."
)
def verify_otp(body: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Checks verification token correctness in Redis and creates register tracker request.
    """
    stored = redis_client.get(f"otp:{body.tax_id}")
    if not stored:
        raise HTTPException(status_code=400, detail={"code": "OTP_EXPIRED"})

    stored_json = json.loads(stored)
    if stored_json["phone"] != body.phone:
        raise HTTPException(status_code=400, detail={"code": "TAX_ID_AND_PHONE_MISMATCH"})
    if str(stored_json["code"]) != body.code:
        raise HTTPException(status_code=400, detail={"code": "PHONE_VALIDATION_CODE_INVALID"})

    req = db.query(RegisterRequestModel).filter_by(tax_id=body.tax_id).first()
    if not req:
        req = RegisterRequestModel(tax_id=body.tax_id)
        db.add(req)

    req.name = body.name
    req.phone = body.phone
    req.register_step = "driver_license"
    db.commit()
    redis_client.delete(f"otp:{body.tax_id}")
    return {"success": True}


@router.post(
    "/driver-license/validate", 
    response_model=SimpleSuccessResponse,
    summary="Validate Driver License",
    description="Ensures the driver license number exists and matches the provided driver profile in the database."
)
def validate_driver_license(body: DriverLicenseRequest, db: Session = Depends(get_db)):
    """
    Performs driver license verification and links trust status to driver profile.
    """
    driver = db.query(Driver).filter_by(tax_id=body.tax_id).first()
    if not driver:
        raise HTTPException(status_code=400, detail={"code": "DRIVER_LICENSE_PENDING_VALIDATION"})
    if driver.driver_license_number != body.driver_license:
        raise HTTPException(status_code=400, detail={"code": "DRIVER_LICENSE_NUMBER_MISMATCH"})

    if body.from_login:
        user = db.query(User).filter_by(tax_id=body.tax_id).first()
        if user:
            user.validated_device = body.device
    else:
        req = db.query(RegisterRequestModel).filter_by(tax_id=body.tax_id).first()
        if req:
            req.trusted_device = body.device
            req.register_step = "password"
    db.commit()
    return {"success": True}


@router.post(
    "/register", 
    status_code=201, 
    response_model=AuthResponse,
    summary="Complete Registration",
    description="Registers a new User, deletes temporary register logs, and issues a standard JWT mobile auth token."
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Finalizes password registration and credentials provisioning for new driver.
    """
    req = db.query(RegisterRequestModel).filter_by(tax_id=body.tax_id).first()
    if not req or req.register_step != "password":
        raise HTTPException(status_code=400, detail={"error": "Fluxo inválido"})
    if req.trusted_device != body.device:
        raise HTTPException(status_code=403, detail={"code": "DEVICE_NOT_VALIDATED"})

    driver = db.query(Driver).filter_by(tax_id=body.tax_id).first()
    try:
        user = User(
            tax_id=body.tax_id,
            name=req.name,
            phone=req.phone,
            validated_device=req.trusted_device,
            driver_id=driver.id if driver else None,
            password_hash=hash_secret(body.password)
        )
        db.add(user)
        db.delete(req)
        db.commit()

        token = generate_jwt(
            {"sub": str(user.id), "tax_id": user.tax_id, "device_id": body.device},
            exp_delta=settings.JWT_EXPIRATION_DELTA_MOBILE
        )
        return {"success": True, "data": {"token": token, "user": {"tax_id": user.tax_id, "name": user.name, "phone": user.phone, "email": user.email}}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post(
    "/login", 
    response_model=AuthResponse,
    summary="Mobile Login",
    description="Authenticates the user using tax ID and password, verifying device validation before returning a JWT."
)
def login(body: MobileLoginRequest, db: Session = Depends(get_db)):
    """
    Verifies user credentials, device trust index, and returns authorization token.
    """
    user = db.query(User).filter_by(tax_id=body.tax_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
    if not verify_secret(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail={"code": "PASSWORD_INVALID"})
    if user.validated_device != body.device:
        raise HTTPException(status_code=403, detail={"code": "DEVICE_NOT_VALIDATED"})

    token = generate_jwt(
        {"sub": str(user.id), "tax_id": user.tax_id, "device_id": body.device},
        exp_delta=settings.JWT_EXPIRATION_DELTA_MOBILE
    )
    return {"success": True, "data": {"token": token, "user": {"name": user.name, "tax_id": user.tax_id, "phone": user.phone, "email": user.email}}}


@router.post(
    "/session/restore", 
    response_model=UserProfileResponse,
    summary="Restore User Session",
    description="Restores active user parameters based on validated session credentials."
)
def restore_session(current_user: User = Depends(get_current_user)):
    """
    Verifies and validates active user credentials.
    """
    return {"success": True, "data": {"user": {
        "tax_id": current_user.tax_id,
        "name": current_user.name,
        "phone": current_user.phone,
        "email": current_user.email
    }}}


@router.delete(
    "/register-request", 
    response_model=SimpleSuccessResponse,
    summary="Delete Registration Request",
    description="Deletes temporary pending request records from database."
)
def delete_registration_request(body: DeleteRegisterRequest, db: Session = Depends(get_db)):
    """
    Disposes of temporary registration request logs.
    """
    req = db.query(RegisterRequestModel).filter_by(tax_id=body.tax_id).first()
    if not req:
        raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND"})
    
    db.delete(req)
    db.commit()
    
    return {"success": True}


@router.post(
    "/profile/phone/verify", 
    response_model=UserProfileResponse,
    summary="Verify & Update Phone Number",
    description="Verifies profile phone update using the numeric verification code stored in Redis."
)
def verify_profile_phone(
    body: ProfilePhoneVerifyRequest, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Checks phone verification token correctness and commits changes to user profiles.
    """
    stored = redis_client.get(f"otp:{current_user.tax_id}")
    if not stored:
        raise HTTPException(status_code=400, detail={"code": "OTP_EXPIRED", "message": "Código expirou ou não foi gerado."})

    stored_json = json.loads(stored)
    if stored_json["phone"] != body.phone:
        raise HTTPException(status_code=400, detail={"code": "PHONE_MISMATCH", "message": "Telefone não corresponde ao código gerado."})
    if str(stored_json["code"]) != body.code:
        raise HTTPException(status_code=400, detail={"code": "PHONE_VALIDATION_CODE_INVALID", "message": "Código inválido."})

    current_user.phone = body.phone
    db.commit()
    redis_client.delete(f"otp:{current_user.tax_id}")
    return {"success": True, "data": {"user": {
        "tax_id": current_user.tax_id,
        "name": current_user.name,
        "phone": current_user.phone,
        "email": current_user.email
    }}}


@router.post(
    "/profile/email/send-code", 
    response_model=SimpleSuccessResponse,
    summary="Send Email Verification Code",
    description="Generates an email verification OTP code, saves it to Redis, and registers email changes request."
)
def send_email_code(body: EmailSendRequest, current_user: User = Depends(get_current_user)):
    """
    Generates and registers OTP for email validation.
    """
    code = random.randint(1000, 9999)
    redis_client.setex(f"otp_email:{current_user.tax_id}", 300, json.dumps({"code": code, "email": body.email}))
    print(f"DEBUG OTP EMAIL {current_user.tax_id}: {code}")
    return {"success": True}


@router.post(
    "/profile/email/verify", 
    response_model=UserProfileResponse,
    summary="Verify & Update Email Address",
    description="Validates email OTP and registers the updated email address if it is not already taken by another account."
)
def verify_profile_email(
    body: EmailVerifyRequest, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Confirms email address uniqueness and validates OTP before committing to database.
    """
    stored = redis_client.get(f"otp_email:{current_user.tax_id}")
    if not stored:
        raise HTTPException(status_code=400, detail={"code": "OTP_EXPIRED", "message": "Código expirou ou não foi gerado."})

    stored_json = json.loads(stored)
    if stored_json["email"] != body.email:
        raise HTTPException(status_code=400, detail={"code": "EMAIL_MISMATCH", "message": "E-mail não corresponde ao código gerado."})
    if str(stored_json["code"]) != body.code:
        raise HTTPException(status_code=400, detail={"code": "EMAIL_VALIDATION_CODE_INVALID", "message": "Código inválido."})

    # Check if email is already taken by another user
    existing_user = db.query(User).filter(User.email == body.email, User.id != current_user.id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail={"code": "EMAIL_ALREADY_TAKEN", "message": "Este e-mail já está cadastrado em outra conta."})

    current_user.email = body.email
    db.commit()
    redis_client.delete(f"otp_email:{current_user.tax_id}")
    return {"success": True, "data": {"user": {
        "tax_id": current_user.tax_id,
        "name": current_user.name,
        "phone": current_user.phone,
        "email": current_user.email
    }}}