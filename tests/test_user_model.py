"""Tests for cantica.models.user and cantica.core.jwt_utils."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest

# Local imports:
from cantica.core.jwt_utils import create_jwt, verify_jwt
from cantica.models.user import Role, User


# ── User model ────────────────────────────────────────────────────────────────


def test_user_has_role():
    user = User(username="alice", roles=[Role.user])
    assert user.has_role(Role.user) is True
    assert user.has_role(Role.admin) is False


def test_user_can_write_admin():
    user = User(username="bob", roles=[Role.admin])
    assert user.can_write() is True
    assert user.is_admin() is True


def test_user_can_write_user():
    user = User(username="carol", roles=[Role.user])
    assert user.can_write() is True
    assert user.is_admin() is False


def test_user_cannot_write_readonly():
    user = User(username="anon", roles=[Role.readonly])
    assert user.can_write() is False
    assert user.is_admin() is False


def test_user_can_read_private():
    assert User(username="u", roles=[Role.admin]).can_read_private() is True
    assert User(username="u", roles=[Role.user]).can_read_private() is True
    assert User(username="u", roles=[Role.readonly]).can_read_private() is False


# ── JWT utils ─────────────────────────────────────────────────────────────────


SECRET = "test-secret-key"


def test_create_and_verify_jwt():
    user = User(id="uid-1", username="alice", email="a@example.com", roles=[Role.admin])
    token = create_jwt(user, SECRET, expire_minutes=60)
    recovered = verify_jwt(token, SECRET)
    assert recovered is not None
    assert recovered.id == "uid-1"
    assert recovered.username == "alice"
    assert Role.admin in recovered.roles


def test_verify_jwt_wrong_secret():
    user = User(username="alice", roles=[Role.user])
    token = create_jwt(user, SECRET)
    assert verify_jwt(token, "wrong-secret") is None


def test_verify_jwt_invalid_token():
    assert verify_jwt("not-a-jwt", SECRET) is None
    assert verify_jwt("", SECRET) is None


def test_verify_jwt_expired(monkeypatch):
    """Expired token should return None."""
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415

    import jwt  # noqa: PLC0415

    user = User(username="bob", roles=[Role.user])
    payload = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "roles": ["user"],
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),  # expired
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    assert verify_jwt(token, SECRET) is None
