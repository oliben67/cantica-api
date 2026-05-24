# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from functools import lru_cache
from typing import Annotated

# Third party imports:
from fastapi import Depends, Header, HTTPException

# Local imports:
from cantica.config import Settings, get_settings
from cantica.core.security import hash_api_key
from cantica.services.version_store import VersionStore


@lru_cache
def get_store() -> VersionStore:
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
