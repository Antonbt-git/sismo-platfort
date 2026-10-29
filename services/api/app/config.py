"""Configuracion central via variables de entorno (.env)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./sismo.sqlite3"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "dev-secret-cambiar"
    access_token_expire_minutes: int = 600
    # NoDecode: se parsea a mano para aceptar tanto JSON
    # ("["https://a.com","https://b.com"]") como lista separada por comas.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    seed_admin_email: str = "admin@sismoplatform.pe"
    seed_admin_password: str = "cambiar-en-produccion"

    ingesta_interval_seconds: int = 300
    ingesta_min_magnitude: float = 2.5
    ingesta_lookback_hours: int = 24

    artifacts_dir: str = "var/artifacts"
    reports_dir: str = "var/reports"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Acepta JSON, lista separada por comas o un unico origen suelto."""
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Tolerante a comillas simples o comas finales: ["https://a", 'https://b',]
                inner = raw.strip("[]")
                parsed = [part.strip().strip("\"'") for part in inner.split(",") if part.strip().strip("\"'")]
            if isinstance(parsed, str):
                return [parsed]
            return parsed
        return [part.strip().strip("\"'") for part in raw.split(",") if part.strip().strip("\"'")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
