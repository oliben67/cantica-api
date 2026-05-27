"""Tests for /v1/admin/* endpoints (user CRUD)."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_auth_config, get_auth_provider, get_settings, get_store
from cantica.config import Settings
from cantica.core.auth_config import AuthConfig
from cantica.core.auth_provider import LocalAuthProvider
from cantica.main import create_app
from cantica.models.user import Role, User
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
    admin_user = User(id="admin-1", username="admin", roles=[Role.admin])
    settings = Settings(vault_path=vault, auth_enabled=False)
    cfg = AuthConfig()
    provider = LocalAuthProvider(store, cfg)

    from cantica.api.deps import get_current_user  # noqa: PLC0415

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_auth_config] = lambda: cfg
    app.dependency_overrides[get_auth_provider] = lambda: provider
    # Inject admin user directly (auth_enabled=False gives local/admin anyway)
    with TestClient(app) as c:
        yield c


# ── GET /v1/admin/users ───────────────────────────────────────────────────────


def test_list_users_empty(client: TestClient):
    r = client.get("/v1/admin/users")
    assert r.status_code == 200
    assert r.json() == []


def test_list_users_after_create(client: TestClient):
    client.post("/v1/admin/users", json={"username": "alice", "password": "p", "roles": ["user"]})
    r = client.get("/v1/admin/users")
    assert r.status_code == 200
    names = [u["username"] for u in r.json()]
    assert "alice" in names


# ── POST /v1/admin/users ──────────────────────────────────────────────────────


def test_create_user_success(client: TestClient):
    r = client.post("/v1/admin/users", json={"username": "bob", "email": "b@example.com", "password": "pass123", "roles": ["admin"]})
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "bob"
    assert data["email"] == "b@example.com"
    assert "admin" in data["roles"]
    assert "id" in data


def test_create_user_duplicate_returns_409(client: TestClient):
    client.post("/v1/admin/users", json={"username": "carol", "password": "p"})
    r = client.post("/v1/admin/users", json={"username": "carol", "password": "p2"})
    assert r.status_code == 409


# ── GET /v1/admin/users/{id} ──────────────────────────────────────────────────


def test_get_user_found(client: TestClient):
    created = client.post("/v1/admin/users", json={"username": "dave", "password": "p"}).json()
    r = client.get(f"/v1/admin/users/{created['id']}")
    assert r.status_code == 200
    assert r.json()["username"] == "dave"


def test_get_user_not_found(client: TestClient):
    r = client.get("/v1/admin/users/no-such-id")
    assert r.status_code == 404


# ── PATCH /v1/admin/users/{id} ────────────────────────────────────────────────


def test_update_user_email(client: TestClient):
    created = client.post("/v1/admin/users", json={"username": "eve", "password": "p"}).json()
    r = client.patch(f"/v1/admin/users/{created['id']}", json={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "new@example.com"


def test_update_user_roles(client: TestClient):
    created = client.post("/v1/admin/users", json={"username": "frank", "password": "p", "roles": ["user"]}).json()
    r = client.patch(f"/v1/admin/users/{created['id']}", json={"roles": ["admin"]})
    assert r.status_code == 200
    assert "admin" in r.json()["roles"]


def test_update_user_password(client: TestClient, store: VersionStore):
    import bcrypt  # noqa: PLC0415

    created = client.post("/v1/admin/users", json={"username": "gina", "password": "old"}).json()
    r = client.patch(f"/v1/admin/users/{created['id']}", json={"password": "new123"})
    assert r.status_code == 200
    row = store.get_user_by_id(created["id"])
    assert bcrypt.checkpw(b"new123", row.password_hash.encode())


def test_update_user_deactivate(client: TestClient):
    created = client.post("/v1/admin/users", json={"username": "hank", "password": "p"}).json()
    r = client.patch(f"/v1/admin/users/{created['id']}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_update_user_not_found(client: TestClient):
    r = client.patch("/v1/admin/users/no-such-id", json={"email": "x@x.com"})
    assert r.status_code == 404


# ── DELETE /v1/admin/users/{id} ───────────────────────────────────────────────


def test_delete_user_success(client: TestClient):
    created = client.post("/v1/admin/users", json={"username": "ivan", "password": "p"}).json()
    r = client.delete(f"/v1/admin/users/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/v1/admin/users/{created['id']}").status_code == 404


def test_delete_user_not_found(client: TestClient):
    r = client.delete("/v1/admin/users/no-such-id")
    assert r.status_code == 404


# ── Role guard: non-admin should be blocked ───────────────────────────────────


def test_admin_endpoint_requires_admin_role():
    """Explicitly test that a non-admin user gets 403."""
    from cantica.api.deps import get_current_user  # noqa: PLC0415

    app = create_app()
    readonly_user = User(id="ro", username="readonly", roles=[Role.readonly])
    app.dependency_overrides[get_current_user] = lambda: readonly_user
    with TestClient(app) as c:
        r = c.get("/v1/admin/users")
    assert r.status_code == 403
