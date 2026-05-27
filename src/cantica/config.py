"""
Application-wide configuration via pydantic-settings.

All settings are read from environment variables prefixed with ``CANTICA_``
and from an optional ``.env`` file in the working directory.

Key settings:

``CANTICA_VAULT_PATH``      (Path, default ``~/.cantica/vault``)
    Root directory for the SQLite database and the blob store.

``CANTICA_DATABASE_URL``    (str, default "")
    Full SQLAlchemy connection URL.  When empty, defaults to
    ``sqlite:///<vault_path>/cantica.db``.

``CANTICA_AUTH_ENABLED``    (bool, default False)
    When True, every API request must supply a valid ``X-API-Key`` header.
    When False, all requests are treated as the ``"local"`` user.

``CANTICA_API_KEY_HEADER``  (str, default ``"X-API-Key"``)
    HTTP header name used to pass API keys.

``CANTICA_HOST``            (str, default ``"0.0.0.0"``)
``CANTICA_PORT``            (int, default ``8042``)
    Bind address / port for the development server.

``CANTICA_LOG_LEVEL``       (str, default ``"info"``)
    Minimum log level passed to the logging subsystem.

``CANTICA_REMOTE_URL``      (str, default "")
    Default base URL for push/pull operations when ``--remote`` is omitted.

``get_settings()`` is ``@lru_cache``-wrapped so the ``Settings`` object is
constructed exactly once per process.  Tests reset it via
``app.dependency_overrides[get_settings]``.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from functools import lru_cache
from pathlib import Path

# Third party imports:
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (prefix: ``CANTICA_``)."""

    vault_path: Path = Path.home() / ".cantica" / "vault"
    database_url: str = ""  # if empty, defaults to sqlite:///<vault_path>/cantica.db
    auth_enabled: bool = False
    api_key_header: str = "X-API-Key"
    host: str = "0.0.0.0"
    port: int = 8042
    log_level: str = "info"
    remote_url: str = ""
    federation_sync_interval: int = 3600  # seconds between background sync cycles

    # User auth / session settings
    auth_config_path: Path | None = None   # path to auth.yaml; None = defaults only
    jwt_secret: str = ""                   # HS256 secret; auto-derived if empty
    jwt_expire_minutes: int = 60           # session token lifetime

    # Federation permissions
    federation_policy_path: Path | None = None  # path to federation-policy.yaml

    # Base URL used in invite emails and QR codes (auto-detected from request if empty)
    base_url: str = ""

    # SMTP — leave smtp_host empty to disable email sending
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@cantica.local"
    smtp_tls: bool = True

    model_config = SettingsConfigDict(env_prefix="CANTICA_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    """Return the cached ``Settings`` singleton (loaded once per process)."""
    return Settings()
