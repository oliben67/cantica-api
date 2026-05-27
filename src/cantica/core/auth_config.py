"""
YAML-based authentication configuration loader.

Config file example (``/etc/cantica/auth.yaml``):

.. code-block:: yaml

    provider: local          # local | oidc | ldap | saml

    # Permissions granted to unauthenticated callers
    anonymous:
      roles: [readonly]      # or [] to block all anonymous access

    local:
      seed_users:
        - username: admin
          email: admin@example.com
          password: changeme   # plaintext — hashed on first import
          roles: [admin]
        - username: alice
          email: alice@example.com
          password: secret
          roles: [user]

If the file does not exist, the module falls back to defaults: provider=local,
anonymous roles=[readonly], no seed users.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path
from typing import Any

# Third party imports:
import yaml
from pydantic import BaseModel, Field


class SeedUser(BaseModel):
    """A user definition in the seed section of auth.yaml."""

    username: str
    email: str = ""
    password: str
    roles: list[str] = Field(default_factory=lambda: ["user"])


class LocalAuthConfig(BaseModel):
    """Settings for the local (username/password) authentication provider."""

    seed_users: list[SeedUser] = Field(default_factory=list)


class AnonymousConfig(BaseModel):
    """Permissions granted to unauthenticated callers."""

    roles: list[str] = Field(default_factory=lambda: ["readonly"])


class AuthConfig(BaseModel):
    """Top-level auth configuration loaded from auth.yaml."""

    provider: str = "local"
    anonymous: AnonymousConfig = Field(default_factory=AnonymousConfig)
    local: LocalAuthConfig = Field(default_factory=LocalAuthConfig)

    @classmethod
    def from_yaml(cls, path: Path | str | None) -> AuthConfig:
        """Load an ``AuthConfig`` from *path*, or return defaults if absent."""
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            return cls()
        raw: dict[str, Any] = yaml.safe_load(p.read_text()) or {}
        return cls.model_validate(raw)
