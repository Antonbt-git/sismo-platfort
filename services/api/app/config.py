"""Configuracion central via variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./sismo.sqlite3"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "dev-secret-cambiar"
    access_token_expire_minutes: int = 600
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    seed_admin_email: str = "admin@sismoplatform.pe"
    seed_admin_password: str = "cambiar-en-produccion"

    ingesta_interval_seconds: int = 300
    ingesta_min_magnitude: float = 2.5
    ingesta_lookback_hours: int = 24

    artifacts_dir: str = "var/artifacts"
    reports_dir: str = "var/reports"


@lru_cache
def get_settings() -> Settings:
    return Settings()
