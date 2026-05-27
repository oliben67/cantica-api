"""
FastAPI dependency injection helpers for the Cantica API.

``StoreDep``     — the shared ``VersionStore`` singleton.
``UserDep``      — the current authenticated (or anonymous) ``User``.
``SettingsDep``  — application settings.
``CertTokenDep`` — optional namespace certificate header.

Auth resolution order (when ``auth_enabled=True``):

1. ``Authorization: Bearer <jwt>``  — JWT session token (web UI login)
2. ``X-API-Key: <key>``             — static API key (CLI / programmatic)
3. No credentials                   — anonymous User built from ``auth.yaml``

When ``auth_enabled=False`` every request receives an admin User with id
``"local"`` (backward-compatible with the original behaviour).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from asyncio import Lock
from functools import lru_cache
from typing import Annotated

# Third party imports:
from fastapi import Depends, Header, HTTPException

# Local imports:
from cantica.config import Settings, get_settings
from cantica.core.auth_config import AuthConfig
from cantica.core.auth_provider import LocalAuthProvider
from cantica.core.federation_policy import FederationPolicy
from cantica.core.jwt_utils import verify_jwt
from cantica.core.security import hash_api_key
from cantica.models.user import Role, User
from cantica.services.version_store import VersionStore


def get_write_lock() -> Lock:
    """Return the write-serialisation lock for this Cantica instance."""
    return Lock()


WriteLockDep = Annotated[Lock, Depends(get_write_lock)]


@lru_cache
def get_store() -> VersionStore:
    """Return the process-wide singleton ``VersionStore``."""
    settings = get_settings()
    settings.vault_path.mkdir(parents=True, exist_ok=True)
    return VersionStore(
        settings.vault_path,
        database_url=settings.database_url or None,
    )


@lru_cache
def get_auth_config() -> AuthConfig:
    """Return the cached ``AuthConfig`` loaded from ``auth_config_path``."""
    settings = get_settings()
    return AuthConfig.from_yaml(settings.auth_config_path)


@lru_cache
def get_auth_provider() -> LocalAuthProvider:
    """Return the cached ``LocalAuthProvider`` singleton."""
    return LocalAuthProvider(get_store(), get_auth_config())


def get_jwt_secret() -> str:
    """Return the JWT signing secret; derive from federation key if unconfigured."""
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    # Derive from the federation private key so the secret survives restarts
    store = get_store()
    key_path = store._federation_key_path()
    if key_path.exists():
        import hashlib  # noqa: PLC0415

        return hashlib.sha256(key_path.read_bytes()).hexdigest()
    # Fallback: deterministic from vault path (not secure for production)
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(str(settings.vault_path).encode()).hexdigest()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
    store: VersionStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    auth_config: AuthConfig = Depends(get_auth_config),
) -> User:
    """FastAPI dependency that returns the authenticated (or anonymous) User."""
    if not settings.auth_enabled:
        return User(id="local", username="local", roles=[Role.admin], is_active=True)

    # 1. JWT bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        user = verify_jwt(token, get_jwt_secret())
        if user is not None:
            return user
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 2. API key
    if x_api_key:
        token_meta = store.verify_api_key(hash_api_key(x_api_key))
        if not token_meta:
            raise HTTPException(status_code=401, detail="Invalid API key")
        # API key holders get `user` role (not admin) unless escalated
        return User(
            id=token_meta["id"],
            username=token_meta["name"],
            roles=[Role.user],
            is_active=True,
        )

    # 3. Anonymous — roles determined by auth.yaml
    anon_roles = [Role(r) for r in auth_config.anonymous.roles]
    return User(id="anonymous", username="anonymous", roles=anon_roles, is_active=True)


@lru_cache
def get_federation_policy() -> FederationPolicy:
    """Return the cached ``FederationPolicy`` loaded from ``federation_policy_path``."""
    settings = get_settings()
    return FederationPolicy.from_yaml(settings.federation_policy_path)


FederationPolicyDep = Annotated[FederationPolicy, Depends(get_federation_policy)]


def require_write_user(user: User = Depends(get_current_user)) -> User:
    """Dependency that rejects anonymous (readonly) callers with HTTP 403."""
    if not user.can_write():
        raise HTTPException(status_code=403, detail="Authentication required to write")
    return user


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency that rejects non-admin callers with HTTP 403."""
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# Convenience type aliases for endpoint signatures
StoreDep = Annotated[VersionStore, Depends(get_store)]
UserDep = Annotated[User, Depends(get_current_user)]
WriteUserDep = Annotated[User, Depends(require_write_user)]
AdminUserDep = Annotated[User, Depends(require_admin_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CertTokenDep = Annotated[str | None, Header(alias="X-Cantica-Certificate")]
