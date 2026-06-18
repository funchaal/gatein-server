import secrets
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from jose import jwt
from config import settings

class APIKeyManager:
    @staticmethod
    def generate_key_pair():
        unique_id = secrets.token_hex(5)
        prefix = f"sk_live_{unique_id}"
        secret_part = secrets.token_urlsafe(32)
        full_key = f"{prefix}_{secret_part}"
        key_hash = generate_password_hash(full_key)
        return full_key, prefix, key_hash

    @staticmethod
    def verify_key(stored_hash: str, provided_key: str) -> bool:
        return check_password_hash(stored_hash, provided_key)

def hash_secret(secret: str) -> str:
    return generate_password_hash(secret)

def verify_secret(stored_hash: str, secret: str) -> bool:
    return check_password_hash(stored_hash, secret)

def generate_jwt(payload: dict, exp_delta: datetime.timedelta = None) -> str:
    data = payload.copy()
    data.setdefault("iat", datetime.datetime.utcnow())
    if exp_delta:
        data["exp"] = datetime.datetime.utcnow() + exp_delta
    return jwt.encode(data, settings.SECRET_KEY, algorithm="HS256")