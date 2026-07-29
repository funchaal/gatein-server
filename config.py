from datetime import timedelta
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "dev_key_super_secret"
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/gatein_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Lê como int (dias) e expõe como timedelta
    JWT_EXPIRATION_DAYS_MOBILE: int = 7
    JWT_EXPIRATION_DAYS_WEB: int = 1

    MASTER_API_KEY: str = "fallback_local_key_se_necessario"
    SUPER_ADMIN_SECRET: str = "senha_super_secreta_de_fallback_apenas_para_dev"

    # Caminho para o arquivo JSON da chave privada do Firebase Admin SDK
    FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"

    # ─── Cloudflare R2 ───────────────────────────────────────────────────────────
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "gatein"
    R2_PUBLIC_URL: str = ""  # Ex: https://pub-xxxx.r2.dev

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    # ─── Log Level ───────────────────────────────────────────────────────────
    # Níveis válidos: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    LOG_LEVEL: str = "INFO"

    # ─── Ambiente ────────────────────────────────────────────────────────────
    # Opções válidas: "development", "homologation", "production"
    ENVIRONMENT: Literal["development", "homologation", "production"] = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_homologation(self) -> bool:
        return self.ENVIRONMENT.lower() == "homologation"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    # Mantido para retrocompatibilidade onde IS_PROD era checado
    @property
    def IS_PROD(self) -> bool:
        return self.is_production

    # ─── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS_STR.split(",") if origin.strip()]

    @property
    def JWT_EXPIRATION_DELTA_MOBILE(self) -> timedelta:
        return timedelta(days=self.JWT_EXPIRATION_DAYS_MOBILE)

    @property
    def JWT_EXPIRATION_DELTA_WEB(self) -> timedelta:
        return timedelta(days=self.JWT_EXPIRATION_DAYS_WEB)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.SECRET_KEY in ("dev_key_super_secret", "minha_chave_secreta_aqui", ""):
                raise ValueError("CRITICAL: SECRET_KEY padrão de desenvolvimento não é permitida em ambiente de produção!")
            if self.SUPER_ADMIN_SECRET in ("senha_super_secreta_de_fallback_apenas_para_dev", "1234", ""):
                raise ValueError("CRITICAL: SUPER_ADMIN_SECRET padrão não é permitida em ambiente de produção!")
            if self.MASTER_API_KEY in ("fallback_local_key_se_necessario", "sua_chave_super_secreta_aqui_12345", ""):
                raise ValueError("CRITICAL: MASTER_API_KEY padrão não é permitida em ambiente de produção!")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()