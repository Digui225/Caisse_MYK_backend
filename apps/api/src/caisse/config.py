from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Caisse MYK API"
    APP_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True
    PORT: int = 8001
    HOST: str = "0.0.0.0"

    # Base de données PostgreSQL
    DATABASE_URL: str = "postgresql+psycopg://caisse:caisse_secret@localhost:5432/caisse"

    # Sécurité & Auth
    JWT_SECRET: str = "default_secret_key_to_be_replaced_in_env_with_at_least_64_random_characters"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_HOURS: int = 12
    PIN_MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # Fuseau horaire
    TZ: str = "Africa/Abidjan"

    # Intégrations
    PRINT_AGENT_URL: str = "http://host.docker.internal:8090"
    ENABLE_HARDWARE_PRINTING: bool = False
    FNE_PROVIDER: Literal["manual", "api", "mock"] = "manual"
    FNE_SYNC_TIMEOUT_SECONDS: float = 4.0
    FNE_API_BASE_URL: str = "http://54.247.95.108/ws"
    FNE_API_KEY: str = ""
    FNE_POINT_OF_SALE: str = "CAISSE-1"
    FNE_ESTABLISHMENT: str = "RESTAURANT CHEZ SYLLA PLUS"
    BACKUP_DIR: str = "/var/backups/caisse"

    @property
    def fne_provider(self) -> str:
        return self.FNE_PROVIDER

    @property
    def fne_sync_timeout_seconds(self) -> float:
        return self.FNE_SYNC_TIMEOUT_SECONDS

    @property
    def fne_api_base_url(self) -> str:
        return self.FNE_API_BASE_URL

    @property
    def fne_api_key(self) -> str:
        return self.FNE_API_KEY

    @property
    def fne_verification_base_url(self) -> str:
        if "54.247.95.108" in self.FNE_API_BASE_URL:
            return "http://54.247.95.108/fr/verification"
        return "https://fne.dgi.gouv.ci/verify"


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
