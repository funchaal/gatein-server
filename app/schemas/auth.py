from pydantic import BaseModel
from typing import Optional

class CheckStatusRequest(BaseModel):
    tax_id: str

class OTPSendRequest(BaseModel):
    tax_id: str
    phone: str

class OTPVerifyRequest(BaseModel):
    tax_id: str
    code: str
    phone: str
    name: str

class DriverLicenseRequest(BaseModel):
    tax_id: str
    driver_license: str
    device: str
    from_login: bool = False

class RegisterRequest(BaseModel):
    tax_id: str
    password: str
    device: str

class DeleteRegisterRequest(BaseModel):
    tax_id: str

class MobileLoginRequest(BaseModel):
    tax_id: str
    password: str
    device: str

class WebLoginRequest(BaseModel):
    username: str
    password: str
    device: Optional[str] = None

class WebDevResetPasswordRequest(BaseModel):
    username: str
    new_password: str

class VerifyCurrentPasswordRequest(BaseModel):
    current_password: str

class ForgotPasswordRequest(BaseModel):
    tax_id: str
    driver_license: str
    device: str

class ValidateForgotCodeRequest(BaseModel):
    tax_id: str
    device: str
    code: str

class ChangePasswordRequest(BaseModel):
    new_password: str

class ProfilePhoneVerifyRequest(BaseModel):
    phone: str
    code: str

class EmailSendRequest(BaseModel):
    email: str

class EmailVerifyRequest(BaseModel):
    email: str
    code: str