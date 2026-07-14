"""Tests for /v1/auth/* endpoints (login, me, logout)."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import bcrypt
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_auth_config, get_auth_provider, get_settings, get_store
from cantica.config import Settings
from cantica.core.auth_config import AuthConfig
from cantica.core.auth_provider import LocalAuthProvider
from cantica.main import create_app
from cantica.services.version_store import VersionStore


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def store(vault: Path) -> VersionStore:
    s = VersionStore(vault)
    yield s
    s.close()


@pytest.fixture
def client(vault: Path, store: VersionStore) -> TestClient:
    app = create_app()
    settings = Settings(vault_path=vault, auth_enabled=True, jwt_secret="test-secret")
    cfg = AuthConfig()
    provider = LocalAuthProvider(store, cfg)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_auth_config] = lambda: cfg
    app.dependency_overrides[get_auth_provider] = lambda: provider
    with TestClient(app) as c:
        yield c


def _create_user(store: VersionStore, username: str = "alice", password: str = "secret") -> str:
    """Insert a user and return the plain-text password."""
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    store.create_user(
        username, email=f"{username}@example.com", password_hash=pw_hash, roles=["user"]
    )
    return password


# ── POST /v1/auth/login ───────────────────────────────────────────────────────


def test_login_success(client: TestClient, store: VersionStore):
    _create_user(store)
    r = client.post("/v1/auth/login", json={"username": "alice", "password": "secret"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"


def test_login_wrong_password(client: TestClient, store: VersionStore):
    _create_user(store)
    r = client.post("/v1/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client: TestClient):
    r = client.post("/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


# ── GET /v1/auth/me ───────────────────────────────────────────────────────────


def test_me_with_valid_jwt(client: TestClient, store: VersionStore):
    _create_user(store)
    login = client.post("/v1/auth/login", json={"username": "alice", "password": "secret"})
    token = login.json()["access_token"]
    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_me_with_invalid_jwt(client: TestClient):
    r = client.get("/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401


def test_me_anonymous(client: TestClient):
    """Without credentials, /me returns the anonymous user."""
    r = client.get("/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "anonymous"


# ── POST /v1/auth/logout ──────────────────────────────────────────────────────


def test_logout(client: TestClient, store: VersionStore):
    _create_user(store)
    login = client.post("/v1/auth/login", json={"username": "alice", "password": "secret"})
    token = login.json()["access_token"]
    r = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
