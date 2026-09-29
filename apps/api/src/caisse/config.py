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
    FNE_PROVIDER: Literal["manual", "api", "mock"] = "manual"
    BACKUP_DIR: str = "/var/backups/caisse"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
