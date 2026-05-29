"""Tests for LocalAuthProvider and version_store user methods."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import bcrypt
import pytest

# Local imports:
from cantica.core.auth_config import AuthConfig, SeedUser
from cantica.core.auth_provider import LocalAuthProvider
from cantica.models.user import Role
from cantica.services.version_store import VersionStore


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path / "vault")
    yield s
    s.close()


@pytest.fixture
def provider(store: VersionStore) -> LocalAuthProvider:
    cfg = AuthConfig()
    return LocalAuthProvider(store, cfg)


# ── VersionStore user methods ──────────────────────────────────────────────────


def test_create_and_get_user_by_username(store: VersionStore):
    user = store.create_user("alice", email="a@example.com", roles=["user"])
    assert user.username == "alice"
    row = store.get_user_by_username("alice")
    assert row is not None
    assert row.email == "a@example.com"


def test_get_user_by_id(store: VersionStore):
    user = store.create_user("bob")
    row = store.get_user_by_id(user.id)
    assert row is not None
    assert row.username == "bob"


def test_get_user_not_found(store: VersionStore):
    assert store.get_user_by_username("nobody") is None
    assert store.get_user_by_id("no-id") is None


def test_list_users(store: VersionStore):
    store.create_user("alice")
    store.create_user("bob")
    users = store.list_users()
    names = {u.username for u in users}
    assert names == {"alice", "bob"}


def test_update_user_email(store: VersionStore):
    user = store.create_user("carol", email="old@example.com")
    updated = store.update_user(user.id, email="new@example.com")
    assert updated is not None
    assert updated.email == "new@example.com"


def test_update_user_roles(store: VersionStore):
    user = store.create_user("dave", roles=["user"])
    updated = store.update_user(user.id, roles=["admin"])
    assert updated is not None
    assert Role.admin in updated.roles


def test_update_user_is_active(store: VersionStore):
    user = store.create_user("eve")
    updated = store.update_user(user.id, is_active=False)
    assert updated is not None
    assert updated.is_active is False


def test_update_user_not_found(store: VersionStore):
    assert store.update_user("no-id") is None


def test_delete_user(store: VersionStore):
    user = store.create_user("frank")
    assert store.delete_user(user.id) is True
    assert store.get_user_by_id(user.id) is None


def test_delete_user_not_found(store: VersionStore):
    assert store.delete_user("no-id") is False


def test_orm_to_user_roles(store: VersionStore):
    user = store.create_user("greta", roles=["admin", "user"])
    row = store.get_user_by_id(user.id)
    converted = store.orm_to_user(row)
    assert Role.admin in converted.roles
    assert Role.user in converted.roles


# ── LocalAuthProvider ─────────────────────────────────────────────────────────


async def test_authenticate_success(store: VersionStore):
    pw_hash = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    store.create_user("han", password_hash=pw_hash, roles=["user"])
    provider = LocalAuthProvider(store, AuthConfig())
    user = await provider.authenticate("han", "secret123")
    assert user is not None
    assert user.username == "han"


async def test_authenticate_wrong_password(store: VersionStore):
    pw_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
    store.create_user("ian", password_hash=pw_hash)
    provider = LocalAuthProvider(store, AuthConfig())
    assert await provider.authenticate("ian", "wrong") is None


async def test_authenticate_unknown_user(provider: LocalAuthProvider):
    assert await provider.authenticate("nobody", "password") is None


async def test_authenticate_inactive_user(store: VersionStore):
    pw_hash = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
    user = store.create_user("jack", password_hash=pw_hash)
    store.update_user(user.id, is_active=False)
    provider = LocalAuthProvider(store, AuthConfig())
    assert await provider.authenticate("jack", "pass") is None


async def test_authenticate_no_password_hash(store: VersionStore):
    store.create_user("kate")  # no password_hash
    provider = LocalAuthProvider(store, AuthConfig())
    assert await provider.authenticate("kate", "anything") is None


async def test_get_user_found(store: VersionStore):
    user = store.create_user("leo")
    provider = LocalAuthProvider(store, AuthConfig())
    result = await provider.get_user(user.id)
    assert result is not None
    assert result.username == "leo"


async def test_get_user_not_found(provider: LocalAuthProvider):
    assert await provider.get_user("no-id") is None


async def test_get_user_inactive(store: VersionStore):
    user = store.create_user("mia")
    store.update_user(user.id, is_active=False)
    provider = LocalAuthProvider(store, AuthConfig())
    assert await provider.get_user(user.id) is None


async def test_get_anonymous_user_default(provider: LocalAuthProvider):
    anon = await provider.get_anonymous_user()
    assert anon.id == "anonymous"
    assert Role.readonly in anon.roles


async def test_get_anonymous_user_empty_roles():
    # Local imports:
    from cantica.core.auth_config import AnonymousConfig  # noqa: PLC0415

    cfg = AuthConfig(anonymous=AnonymousConfig(roles=[]))
    provider = LocalAuthProvider(None, cfg)  # type: ignore[arg-type]
    anon = await provider.get_anonymous_user()
    assert anon.roles == []


async def test_bootstrap_seeds_users(store: VersionStore):
    cfg = AuthConfig.model_validate({
        "local": {
            "seed_users": [
                {"username": "seeded", "email": "s@example.com", "password": "pw", "roles": ["admin"]}
            ]
        }
    })
    provider = LocalAuthProvider(store, cfg)
    await provider.bootstrap()
    row = store.get_user_by_username("seeded")
    assert row is not None
    assert "admin" in row.roles_json


async def test_bootstrap_idempotent(store: VersionStore):
    cfg = AuthConfig.model_validate({
        "local": {"seed_users": [{"username": "dup", "password": "pw"}]}
    })
    provider = LocalAuthProvider(store, cfg)
    await provider.bootstrap()
    await provider.bootstrap()  # second call must not raise or duplicate
    assert len(store.list_users()) == 1
