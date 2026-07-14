"""Tests for flag-gated auth + key-based authentication (remote-mode spec, phase 7).

Covers: invite acceptance with admin review (newbie), the per-request flag
gate, key enrolment (/v1/auth/register), and assertion login (/v1/auth/assert).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import time
import uuid
from pathlib import Path

# Third party imports:
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings as deps_get_settings
from cantica.api.deps import get_store
from cantica.config import Settings
from cantica.core.jwt_utils import create_jwt
from cantica.main import create_app
from cantica.models.user import Role, User
from cantica.services.version_store import VersionStore

_JWT_SECRET = "keyauth-test-secret-xxxxxxxxxxxxxxxxxxxx"


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )


def _assertion(
    private_pem: str, subject: str, *, iat_offset: int = 0, jti: str | None = None
) -> str:
    now = int(time.time()) + iat_offset
    payload = {
        "iss": subject,
        "sub": subject,
        "aud": "cantica-api",
        "iat": now,
        "exp": now + 300,
        "jti": jti or str(uuid.uuid4()),
    }
    return pyjwt.encode(payload, private_pem, algorithm="RS256")


@pytest.fixture
def keyauth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, VersionStore]:
    """Auth-enabled client with manual activation (auto_activate_users=False)."""
    vault = tmp_path / "vault"
    store = VersionStore(vault)
    settings = Settings(
        vault_path=vault,
        auth_enabled=True,
        jwt_secret=_JWT_SECRET,
        auto_activate_users=False,
    )
    # DI overrides for Depends(...) call sites; monkeypatches for lazy direct calls.
    monkeypatch.setattr("cantica.config.get_settings", lambda: settings)
    monkeypatch.setattr("cantica.api.deps.get_settings", lambda: settings)

    app = create_app()
    app.dependency_overrides[deps_get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, store
    store.close()


def _make_active_user(store: VersionStore, username: str = "alice") -> User:
    user = store.create_user(username=username, email=f"{username}@x.com", roles=["user"])
    return user


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_jwt(user, _JWT_SECRET, expire_minutes=5)}"}


# ── Invite acceptance with admin review (spec C.2.a) ──────────────────────────


def test_invite_accept_creates_disabled_newbie(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    invite = store.create_invite("newbie@x.com", created_by="admin", expires_in_hours=24)

    r = client.post(
        f"/v1/invites/{invite['token']}/accept",
        json={"username": "newbie", "password": "Pw123456!", "email": "newbie@x.com"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["user"]["is_active"] is False

    row = store.get_user_by_username("newbie")
    assert row is not None and not row.is_active
    assert "newbie" in store.list_user_flags(row.id)

    # The JWT from acceptance cannot be used until an admin activates the account.
    token = r.json()["access_token"]
    assert (
        client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )

    # Activation (what the admin screen does): enable + clear newbie.
    store.update_user(row.id, is_active=True)
    store.remove_user_flag(row.id, "newbie")
    assert (
        client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    )


# ── Flag gate on live tokens (spec AUTH F) ────────────────────────────────────


def test_blocked_flag_invalidates_live_jwt(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    user = _make_active_user(store)
    h = _bearer(user)
    assert client.get("/v1/auth/me", headers=h).status_code == 200

    store.add_user_flag(user.id, "blocked:abuse", comment="spam")
    r = client.get("/v1/auth/me", headers=h)
    assert r.status_code == 401
    assert "blocked" not in r.text.lower()  # generic body — no state disclosure


def test_warning_flag_still_authenticates(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    user = _make_active_user(store, "warned")
    store.add_user_flag(user.id, "warning:suspicious")
    assert client.get("/v1/auth/me", headers=_bearer(user)).status_code == 200


def test_deactivation_invalidates_live_jwt(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    user = _make_active_user(store, "gone")
    h = _bearer(user)
    assert client.get("/v1/auth/me", headers=h).status_code == 200
    store.update_user(user.id, is_active=False)
    assert client.get("/v1/auth/me", headers=h).status_code == 401


# ── Key enrolment (spec 3–8) ──────────────────────────────────────────────────


def _enrol(client: TestClient, store: VersionStore, username: str = "keyed") -> tuple[str, str]:
    user = _make_active_user(store, username)
    priv, pub = _keypair()
    r = client.post(
        "/v1/auth/register",
        json={"assertion": _assertion(priv, username), "public_key_pem": pub},
        headers=_bearer(user),
    )
    assert r.status_code == 201, r.text
    return priv, r.json()["cantica_user_id"]


def test_enrolment_binds_email_as_cantica_user_id(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    _priv, cuid = _enrol(client, store)
    assert cuid == "keyed@x.com"


def test_enrolment_requires_authentication(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, _store = keyauth
    priv, pub = _keypair()
    r = client.post(
        "/v1/auth/register", json={"assertion": _assertion(priv, "x"), "public_key_pem": pub}
    )
    assert r.status_code == 401


def test_enrolment_rejects_private_key_material(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    user = _make_active_user(store, "leaky")
    priv, _pub = _keypair()
    r = client.post(
        "/v1/auth/register",
        json={"assertion": _assertion(priv, "leaky"), "public_key_pem": priv},
        headers=_bearer(user),
    )
    assert r.status_code == 401


def test_second_enrolment_conflicts(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    _enrol(client, store, "double")
    user_row = store.get_user_by_username("double")
    assert user_row is not None
    priv2, pub2 = _keypair()
    user = User(
        id=user_row.id, username="double", email=user_row.email, roles=[Role.user], is_active=True
    )
    r = client.post(
        "/v1/auth/register",
        json={"assertion": _assertion(priv2, "double"), "public_key_pem": pub2},
        headers=_bearer(user),
    )
    assert r.status_code == 409


# ── Assertion login (spec AUTH A–E) ───────────────────────────────────────────


def test_assert_exchanges_signature_for_session(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "signer")
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid)})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["username"] == "signer"


def test_assert_rejects_jti_replay(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "replayer")
    assertion = _assertion(priv, cuid)
    assert client.post("/v1/auth/assert", json={"assertion": assertion}).status_code == 200
    assert client.post("/v1/auth/assert", json={"assertion": assertion}).status_code == 401


def test_assert_rejects_wrong_key(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    _priv, cuid = _enrol(client, store, "victim")
    attacker_priv, _ = _keypair()
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(attacker_priv, cuid)})
    assert r.status_code == 401


def test_assert_rejects_stale_assertion(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "stale")
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid, iat_offset=-3600)})
    assert r.status_code == 401


def test_assert_denied_for_blocked_user(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "banned")
    row = store.get_user_by_username("banned")
    assert row is not None
    store.add_user_flag(row.id, "blocked:none")
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid)})
    assert r.status_code == 401
    assert "blocked" not in r.text.lower()


def test_assert_returns_warnings(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "warnedkey")
    row = store.get_user_by_username("warnedkey")
    assert row is not None
    store.add_user_flag(row.id, "warning:abuse")
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid)})
    assert r.status_code == 200
    assert r.json()["warnings"] == ["warning:abuse"]


def test_revoked_key_stops_authenticating(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, store = keyauth
    priv, cuid = _enrol(client, store, "revoked")
    key = store.get_active_jwt_key(cuid)
    assert key is not None
    assert store.revoke_jwt_key(key.id)
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid)})
    assert r.status_code == 401


def test_assert_unknown_cantica_user_id(keyauth: tuple[TestClient, VersionStore]) -> None:
    client, _store = keyauth
    priv, _ = _keypair()
    r = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, "ghost@x.com")})
    assert r.status_code == 401
