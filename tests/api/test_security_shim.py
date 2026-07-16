"""Phase C — cantica-api mounted on the cantica-secure shim (CANTICA_SECURITY_SHIM=1).

Proves the flag-on configuration serves the security surface via the package
and that Cantica's domain endpoints still authorize through the adapted
principal (anonymous read access preserved). The in-repo security suites keep
running in the default, flag-off configuration.
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
from cantica_secure.api.deps import CurrentUser
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings as deps_get_settings
from cantica.api.deps import get_store
from cantica.config import Settings
from cantica.core.security_shim import to_cantica_user
from cantica.main import create_app
from cantica.models.user import Role
from cantica.services.version_store import VersionStore

_ADMIN_EMAIL = "admin@shim.local"
_ADMIN_PASS = "ShimTest1234!"
_JWT_SECRET = "cantica-shim-test-secret-xxxxxxxxxxxxxxxx"


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


def _assertion(private_pem: str, subject: str, *, extra: dict | None = None) -> str:
    now = int(time.time())
    payload = {
        "iss": subject,
        "sub": subject,
        "aud": "cantica-secure",
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        **(extra or {}),
    }
    return pyjwt.encode(payload, private_pem, algorithm="RS256")


@pytest.fixture
def shim_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, VersionStore]:
    vault = tmp_path / "vault"
    store = VersionStore(vault)
    settings = Settings(
        vault_path=vault,
        auth_enabled=True,
        security_shim=True,
        jwt_secret=_JWT_SECRET,
        secure_admin_email=_ADMIN_EMAIL,
        secure_admin_password=_ADMIN_PASS,
    )
    monkeypatch.setattr("cantica.config.get_settings", lambda: settings)
    monkeypatch.setattr("cantica.api.deps.get_settings", lambda: settings)

    app = create_app()
    app.dependency_overrides[deps_get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, store
    store.close()


def _admin(client: TestClient) -> dict:
    r = client.post("/v1/auth/login", json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASS})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── principal adapter unit ────────────────────────────────────────────────────


def test_principal_adapter_maps_roles() -> None:
    admin = to_cantica_user(CurrentUser(user_id="u1", email="a@x.com", roles=["admin"]))
    assert admin.roles == [Role.admin]
    assert admin.is_admin()

    # limbo (unknown to Cantica's enum) is dropped; an authenticated principal
    # with no mappable role still counts as user so it can write.
    limbo = to_cantica_user(CurrentUser(user_id="u2", email="b@x.com", roles=["limbo"]))
    assert limbo.roles == []

    anon = to_cantica_user(CurrentUser(user_id="anonymous", email="", roles=["readonly"]))
    assert anon.roles == [Role.readonly]


# ── shim serves the security surface ──────────────────────────────────────────


def test_shim_security_routes_served(shim_client: tuple[TestClient, VersionStore]) -> None:
    client, _ = shim_client
    roles = {r["name"] for r in client.get("/v1/roles", headers=_admin(client)).json()}
    assert roles == {"admin", "user", "readonly", "limbo"}
    # Package-only endpoint — proves the shim is answering.
    assert client.get("/v1/security/ui-config").json()["app_name"] == "Cantica"


def test_anonymous_read_allowed_through_shim(shim_client: tuple[TestClient, VersionStore]) -> None:
    client, _ = shim_client
    # Anonymous readers can list public prompts (auth.yaml semantics preserved).
    assert client.get("/v1/prompts").status_code == 200


def test_admin_can_manage_users_through_shim(shim_client: tuple[TestClient, VersionStore]) -> None:
    client, _ = shim_client
    h = _admin(client)
    u = client.post(
        "/v1/users", json={"email": "new@x.com", "password": "Pw123456!"}, headers=h
    ).json()
    assert u["email"] == "new@x.com"
    assert any(x["email"] == "new@x.com" for x in client.get("/v1/users", headers=h).json())


def test_blocked_flag_blocks_domain_access_through_shim(
    shim_client: tuple[TestClient, VersionStore],
) -> None:
    client, _ = shim_client
    h = _admin(client)
    u = client.post(
        "/v1/users", json={"email": "blk@x.com", "password": "Pw123456!"}, headers=h
    ).json()
    client.post(f"/v1/users/{u['id']}/roles/user", headers=h)
    tok = client.post(
        "/v1/auth/login", json={"email": "blk@x.com", "password": "Pw123456!"}
    ).json()["access_token"]
    bh = {"Authorization": f"Bearer {tok}"}
    # A user role can read prompts.
    assert client.get("/v1/prompts", headers=bh).status_code == 200

    client.post(f"/v1/users/{u['id']}/flags", json={"flag": "blocked:abuse"}, headers=h)
    # Blocked → the shim denies; anonymous fallback does not apply to a
    # presented-but-rejected credential.
    r = client.get("/v1/prompts", headers=bh)
    assert r.status_code == 401
    assert "blocked" not in r.text.lower()


def test_key_enrolment_and_assert_through_shim(
    shim_client: tuple[TestClient, VersionStore],
) -> None:
    client, _ = shim_client
    invitation = client.post(
        "/v1/auth/invitations",
        json={"first_name": "K", "last_name": "E", "email": "keyed@x.com"},
    ).json()["invitation"]
    priv, pub = _keypair()
    r = client.post(
        "/v1/auth/register",
        json={
            "assertion": _assertion(priv, "keyed", extra={"invitation": invitation}),
            "public_key_pem": pub,
        },
    )
    assert r.status_code == 200
    cuid = r.json()["cantica_user_id"]

    ar = client.post("/v1/auth/assert", json={"assertion": _assertion(priv, cuid)})
    # auto_activate_users defaults True on Cantica → the account is usable at once.
    assert ar.status_code == 200
    tok = ar.json()["access_token"]
    assert client.get("/v1/prompts", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_principal_adapter_anonymous_without_roles_gets_anonymous_role() -> None:
    # Anonymous principal with no configured roles falls back to Role.anonymous.
    anon = to_cantica_user(CurrentUser(user_id="anonymous", email="", roles=[]))
    assert anon.roles == [Role.anonymous]
    assert anon.username == "anonymous"


def test_shim_builder_derives_jwt_secret_when_unset(tmp_path: Path) -> None:
    # Empty jwt_secret → derived from vault_path (matches in-repo get_jwt_secret).
    # Local imports:
    from cantica.core.security_shim import build_security_shim

    settings = Settings(
        vault_path=tmp_path / "v",
        auth_enabled=True,
        security_shim=True,
        jwt_secret="",
        secure_admin_password="Pw12345678!",
    )
    shim = build_security_shim(settings)
    try:
        assert len(shim.config.jwt_secret) == 64  # sha256 hex digest
    finally:
        shim.dispose()
