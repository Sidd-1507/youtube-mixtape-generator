"""
backend/core/config.py
----------------------
Centralised settings loaded from .env (or environment variables).
Uses pydantic-settings so every value is type-checked at startup.

Usage anywhere in the backend:
    from backend.core.config import settings
    path = settings.STORAGE_PATH / session_id
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Where session folders are created (e.g. backend/storage/<session_id>/)
    STORAGE_PATH: Path = Path("backend/storage")

    # FastAPI server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # pydantic-settings v2: reads from .env automatically
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Singleton — import this everywhere
settings = Settings()

# Ensure the base storage directory exists when the module is first imported
settings.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
