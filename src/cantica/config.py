# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from functools import lru_cache
from pathlib import Path

# Third party imports:
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    vault_path: Path = Path.home() / ".cantica" / "vault"
    database_url: str = ""  # if empty, defaults to sqlite:///<vault_path>/cantica.db
    auth_enabled: bool = False
    api_key_header: str = "X-API-Key"
    host: str = "0.0.0.0"
    port: int = 8042
    log_level: str = "info"
    remote_url: str = ""

    model_config = SettingsConfigDict(env_prefix="CANTICA_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
