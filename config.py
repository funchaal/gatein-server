from datetime import timedelta
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
    # Gerado em: Firebase Console → Configurações do Projeto → Contas de Serviço
    FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"

    # ─── Ambiente ────────────────────────────────────────────────────────────
    # True  → Produção  (regras de isolamento multi-tenant INATIVAS)
    # False → Staging   (regras de isolamento multi-tenant ATIVAS via ORM event)
    PROD: bool = True

    @property
    def IS_PROD(self) -> bool:
        return self.PROD

    @property
    def JWT_EXPIRATION_DELTA_MOBILE(self) -> timedelta:
        return timedelta(days=self.JWT_EXPIRATION_DAYS_MOBILE)

    @property
    def JWT_EXPIRATION_DELTA_WEB(self) -> timedelta:
        return timedelta(days=self.JWT_EXPIRATION_DAYS_WEB)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()