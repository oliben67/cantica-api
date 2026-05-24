"""
FastAPI dependency injection helpers for the Cantica API.

This module defines the three ``Annotated`` type aliases that endpoint
functions declare as parameters to receive injected dependencies:

``StoreDep``    — ``Annotated[VersionStore, Depends(get_store)]``
    The shared ``VersionStore`` singleton (lru_cache-wrapped, one instance per
    process).  Tests replace it via
    ``app.dependency_overrides[get_store] = lambda: test_store``.

``UserDep``     — ``Annotated[dict[str, str], Depends(get_current_user)]``
    The authenticated user as ``{"id": ..., "name": ...}``.  When
    ``CANTICA_AUTH_ENABLED`` is False every request gets ``{"id": "local",
    "name": "local"}``.  When True, the ``X-API-Key`` header is verified
    against the hashed keys in the database; missing or invalid keys raise
    HTTP 401.

``SettingsDep`` — ``Annotated[Settings, Depends(get_settings)]``
    The application settings (also lru_cache-wrapped).

``CertTokenDep`` — ``Annotated[str | None, Header(alias="X-Cantica-Certificate")]``
    The optional namespace certificate token passed in the
    ``X-Cantica-Certificate`` HTTP header.  Present when the caller holds a
    certificate for a proprietary namespace.

``get_store()``
    Reads ``vault_path`` and ``database_url`` from settings, ensures the vault
    directory exists, and returns a single ``VersionStore`` instance shared
    across all requests in the process lifetime.
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
from cantica.core.security import hash_api_key
from cantica.services.version_store import VersionStore


def get_write_lock() -> Lock:
    """Return the write-serialisation lock for this Cantica instance.

    The default returns a fresh (unshared) lock — fine for standalone servers
    where the database handles concurrency.  ``CanticaShim.mount()`` overrides
    this to return the shim's shared lock so that a streaming push blocks all
    other writes for the duration of ingestion.
    """
    return Lock()


WriteLockDep = Annotated[Lock, Depends(get_write_lock)]


@lru_cache
def get_store() -> VersionStore:
    """Return the process-wide singleton ``VersionStore`` (cached via ``lru_cache``)."""
    settings = get_settings()
    settings.vault_path.mkdir(parents=True, exist_ok=True)
    return VersionStore(
        settings.vault_path,
        database_url=settings.database_url or None,
    )


def get_current_user(
    x_api_key: Annotated[str | None, Header()] = None,
    store: VersionStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """FastAPI dependency that returns the authenticated user or raises 401."""
    if not settings.auth_enabled:
        return {"id": "local", "name": "local"}

    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    user = store.verify_api_key(hash_api_key(x_api_key))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# Convenience type aliases for endpoint signatures
StoreDep = Annotated[VersionStore, Depends(get_store)]
UserDep = Annotated[dict[str, str], Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CertTokenDep = Annotated[str | None, Header(alias="X-Cantica-Certificate")]
