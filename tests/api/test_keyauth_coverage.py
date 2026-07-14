"""Coverage for remote-auth edge branches: gate/keyauth internals, invite
endpoints, admin invite creation, mailer, and store no-op paths."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Third party imports:
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings as deps_get_settings
from cantica.api.deps import get_store
from cantica.config import Settings
from cantica.core.auth_gate import (
    KeyAssertionError,
    gate_user,
    reject_private_key_material,
    verify_assertion,
)
from cantica.core.jwt_utils import create_jwt
from cantica.core.mailer import send_invite
from cantica.main import create_app
from cantica.models.user import Role, User
from cantica.services.version_store import VersionStore
from tests.api.test_keyauth import _assertion, _keypair

_JWT_SECRET = "coverage-test-secret-xxxxxxxxxxxxxxxxxxx"


@pytest.fixture
def cov_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, VersionStore]:
    vault = tmp_path / "vault"
    store = VersionStore(vault)
    settings = Settings(vault_path=vault, auth_enabled=True, jwt_secret=_JWT_SECRET)
    monkeypatch.setattr("cantica.config.get_settings", lambda: settings)
    monkeypatch.setattr("cantica.api.deps.get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[deps_get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, store
    store.close()


@pytest.fixture
def noauth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    vault = tmp_path / "vault"
    store = VersionStore(vault)
    settings = Settings(vault_path=vault, auth_enabled=False)
    monkeypatch.setattr("cantica.config.get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[deps_get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    store.close()


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_jwt(user, _JWT_SECRET, expire_minutes=5)}"}


# ── auth_gate internals ───────────────────────────────────────────────────────


def test_gate_user_none_denied() -> None:
    result = gate_user(None, {}, context="test")
    assert not result.allowed
    assert result.audit_reason == "not found"


def test_reject_non_pem_material() -> None:
    with pytest.raises(KeyAssertionError, match="not a PEM public key"):
        reject_private_key_material("garbage")


def test_verify_assertion_missing_iat() -> None:
    priv, pub = _keypair()
    token = pyjwt.encode(
        {"sub": "x", "exp": int(time.time()) + 300, "jti": str(uuid.uuid4())},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(KeyAssertionError, match="missing iat"):
        verify_assertion(token, pub, max_age_seconds=300)


def test_verify_assertion_stale_iat_with_valid_exp() -> None:
    # exp is still valid, but iat is far outside the freshness window.
    priv, pub = _keypair()
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "x", "iat": now - 3600, "exp": now + 300, "jti": str(uuid.uuid4())},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(KeyAssertionError, match="freshness"):
        verify_assertion(token, pub, max_age_seconds=300)


def test_verify_assertion_missing_jti() -> None:
    priv, pub = _keypair()
    now = int(time.time())
    token = pyjwt.encode({"sub": "x", "iat": now, "exp": now + 300}, priv, algorithm="RS256")
    with pytest.raises(KeyAssertionError, match="missing jti"):
        verify_assertion(token, pub, max_age_seconds=300)


# ── keyauth endpoint edges ────────────────────────────────────────────────────


def test_register_noop_when_auth_disabled(noauth_client: TestClient) -> None:
    r = noauth_client.post("/v1/auth/register", json={"assertion": "x", "public_key_pem": "y"})
    assert r.status_code == 201
    assert r.json() == {"status": "ok", "mode": "local"}


def test_assert_unavailable_when_auth_disabled(noauth_client: TestClient) -> None:
    r = noauth_client.post("/v1/auth/assert", json={"assertion": "x.y.z"})
    assert r.status_code == 400


def test_register_rejects_jwt_for_deleted_user(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, _store = cov_client
    ghost = User(id="ghost-id", username="ghost", roles=[Role.user])
    priv, pub = _keypair()
    r = client.post(
        "/v1/auth/register",
        json={"assertion": _assertion(priv, "ghost"), "public_key_pem": pub},
        headers=_bearer(ghost),
    )
    assert r.status_code == 401


def test_register_rejects_replayed_assertion(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, store = cov_client
    a = store.create_user(username="ra", email="ra@x.com")
    b = store.create_user(username="rb", email="rb@x.com")
    priv, pub = _keypair()
    assertion = _assertion(priv, "shared")
    ok = client.post(
        "/v1/auth/register",
        json={"assertion": assertion, "public_key_pem": pub},
        headers=_bearer(a),
    )
    assert ok.status_code == 201
    replay = client.post(
        "/v1/auth/register",
        json={"assertion": assertion, "public_key_pem": pub},
        headers=_bearer(b),
    )
    assert replay.status_code == 401


def test_assert_rejects_malformed_token(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, _store = cov_client
    r = client.post("/v1/auth/assert", json={"assertion": "not-a-jwt"})
    assert r.status_code == 401


def test_gate_skipped_for_jwt_user_missing_from_db(
    cov_client: tuple[TestClient, VersionStore],
) -> None:
    """JWT users without a DB row (e.g. pre-migration tokens) pass through ungated."""
    client, _store = cov_client
    ghost = User(id="no-row", username="ghost", roles=[Role.user])
    assert client.get("/v1/auth/me", headers=_bearer(ghost)).status_code == 200


# ── invite endpoints (validate + accept edges) ────────────────────────────────


def test_validate_invite_unknown_token(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, _store = cov_client
    r = client.get("/v1/invites/nope")
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_validate_invite_used_and_expired(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, store = cov_client
    used = store.create_invite("used@x.com", created_by="a", expires_in_hours=24)
    u = store.create_user(username="consumer", email="used@x.com")
    store.use_invite(used["token"], u.id)
    assert client.get(f"/v1/invites/{used['token']}").json()["valid"] is False

    expired = store.create_invite("late@x.com", created_by="a", expires_in_hours=-1)
    assert client.get(f"/v1/invites/{expired['token']}").json()["valid"] is False


def test_validate_invite_ok(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, store = cov_client
    inv = store.create_invite("fresh@x.com", created_by="a", expires_in_hours=24)
    body = client.get(f"/v1/invites/{inv['token']}").json()
    assert body["valid"] is True
    assert body["email"] == "fresh@x.com"


def test_accept_invite_used_expired_and_username_taken(
    cov_client: tuple[TestClient, VersionStore],
) -> None:
    client, store = cov_client
    payload = {"username": "someone", "password": "Pw123456!", "email": ""}

    assert client.post("/v1/invites/bogus/accept", json=payload).status_code == 400

    expired = store.create_invite("exp@x.com", created_by="a", expires_in_hours=-1)
    assert client.post(f"/v1/invites/{expired['token']}/accept", json=payload).status_code == 400

    store.create_user(username="taken", email="t@x.com")
    inv = store.create_invite("new@x.com", created_by="a", expires_in_hours=24)
    taken = client.post(
        f"/v1/invites/{inv['token']}/accept",
        json={"username": "taken", "password": "Pw123456!", "email": ""},
    )
    assert taken.status_code == 409


# ── admin invite creation + mailer ────────────────────────────────────────────


def test_admin_creates_and_lists_invites(cov_client: tuple[TestClient, VersionStore]) -> None:
    client, store = cov_client
    admin = store.create_user(username="root", email="root@x.com", roles=["admin"])
    h = _bearer(admin)
    r = client.post("/v1/admin/invites", json={"email": "invitee@x.com"}, headers=h)
    assert r.status_code == 201, r.text
    assert "token=" in r.json()["invite_url"]

    listed = client.get("/v1/admin/invites", headers=h)
    assert listed.status_code == 200
    assert any(i["email"] == "invitee@x.com" for i in listed.json())


def test_send_invite_noop_without_smtp_host() -> None:
    # Must not raise and must not attempt any network I/O.
    send_invite(
        to_email="x@y.z",
        invite_url="http://inv",
        smtp_host="",
        smtp_port=25,
        smtp_user="",
        smtp_password="",
        smtp_from="",
        smtp_tls=True,
    )


def test_send_invite_uses_smtp_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict = {}

    class _FakeSMTP:
        def __init__(self, host: str, port: int) -> None:
            sent["host"], sent["port"] = host, port

        def __enter__(self) -> _FakeSMTP:
            return self

        def __exit__(self, *a: object) -> None: ...

        def starttls(self) -> None:
            sent["tls"] = True

        def login(self, user: str, password: str) -> None:
            sent["login"] = (user, password)

        def sendmail(self, sender: str, to: list[str], _msg: str) -> None:
            sent["from"], sent["to"] = sender, to

    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    send_invite(
        to_email="x@y.z",
        invite_url="http://inv",
        smtp_host="mail.example",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_from="noreply@example",
        smtp_tls=True,
    )
    assert sent["host"] == "mail.example"
    assert sent["tls"] is True
    assert sent["to"] == ["x@y.z"]


# ── store no-op branches ──────────────────────────────────────────────────────


def test_store_flag_and_key_noop_paths(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "vault")
    try:
        user = store.create_user(username="np", email="np@x.com")

        store.add_user_flag(user.id, "warning:none")
        store.add_user_flag(user.id, "warning:none")  # duplicate → no-op
        assert list(store.list_user_flags(user.id)) == ["warning:none"]
        store.remove_user_flag(user.id, "absent")  # absent → no-op

        assert store.get_user_by_email("np@x.com") is not None
        assert store.get_user_by_email("ghost@x.com") is None

        assert store.revoke_jwt_key("missing") is False
        store.touch_jwt_key("missing")  # missing → no-op

        # jti pruning: expired entries are removed, allowing re-use afterwards.
        past = datetime.now(UTC) - timedelta(seconds=1)
        assert store.burn_jti("j1", "auth", past) is True
        assert store.burn_jti("j2", "auth", datetime.now(UTC) + timedelta(seconds=60)) is True
        assert store.burn_jti("j1", "auth", datetime.now(UTC) + timedelta(seconds=60)) is True
    finally:
        store.close()
