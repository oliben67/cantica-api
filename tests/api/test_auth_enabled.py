# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings, get_store
from cantica.config import Settings
from cantica.core.security import generate_api_key
from cantica.main import create_app
from cantica.services.version_store import VersionStore


@pytest.fixture
def auth_store(tmp_path: Path) -> VersionStore:
    vault = tmp_path / "vault"
    store = VersionStore(vault)
    yield store
    store.close()


@pytest.fixture
def auth_client(auth_store: VersionStore, tmp_path: Path) -> TestClient:
    vault = tmp_path / "vault"
    app = create_app()
    settings = Settings(vault_path=vault, auth_enabled=True)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: auth_store
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _insert_key(store: VersionStore, name: str = "test") -> str:
    raw, key_hash = generate_api_key()
    store.create_api_key(name, key_hash)
    return raw


def test_missing_key_returns_401(auth_client: TestClient) -> None:
    r = auth_client.get("/v1/prompts")
    assert r.status_code == 401
    assert "required" in r.json()["detail"]


def test_invalid_key_returns_401(auth_client: TestClient) -> None:
    r = auth_client.get("/v1/prompts", headers={"X-API-Key": "bad-key"})
    assert r.status_code == 401
    assert "Invalid" in r.json()["detail"]


def test_valid_key_is_accepted(auth_client: TestClient, auth_store: VersionStore) -> None:
    raw = _insert_key(auth_store)
    r = auth_client.get("/v1/prompts", headers={"X-API-Key": raw})
    assert r.status_code == 200


def test_valid_key_updates_last_used(auth_client: TestClient, auth_store: VersionStore) -> None:
    raw = _insert_key(auth_store)
    auth_client.get("/v1/prompts", headers={"X-API-Key": raw})
    keys = auth_store.list_api_keys()
    assert keys[0][3] is not None
