"""Tests for the federation membership protocol endpoints (/v1/federate, /v1/federations, /v1/identity)."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings, get_store
from cantica.config import Settings
from cantica.core.federation_crypto import (
    derive_encryption_key,
    encrypt_for,
    generate_key_pair,
    sign_message,
)
from cantica.main import create_app
from cantica.services.version_store import VersionStore

# ── Fixtures ──────────────────────────────────────────────────────────────────


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
    test_settings = Settings(vault_path=vault, auth_enabled=False)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c


@pytest.fixture
def federation(store: VersionStore, client: TestClient):
    """Create a federation via the API and return the JSON response."""
    store.get_or_create_identity()
    r = client.post("/v1/federations", json={"name": "test-fed"})
    assert r.status_code == 201
    return r.json()


def _make_http_mock(json_data: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient that responds with *json_data*."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=json_data)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


def _make_http_error_mock(exc: Exception) -> MagicMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=exc)
    return mock_client


def _signed_request(store: VersionStore, **kwargs) -> dict:
    """Build a FederateRequest body with a valid RSA-PSS signature."""
    # Local imports:
    from cantica.schemas.federate import FederateRequest  # noqa: PLC0415

    payload = FederateRequest(signature="", **kwargs)
    # Standard library imports:
    import json as _json  # noqa: PLC0415

    canonical = _json.dumps(payload.model_dump(exclude={"signature"}), sort_keys=True).encode()
    sig = store.sign_federation_message(canonical)
    return FederateRequest(signature=sig, **kwargs).model_dump()


# ── GET /v1/identity ──────────────────────────────────────────────────────────


def test_get_identity_returns_public_key(client: TestClient, store: VersionStore) -> None:
    r = client.get("/v1/identity")
    assert r.status_code == 200
    data = r.json()
    assert data["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")
    assert "created_at" in data


def test_get_identity_idempotent(client: TestClient, store: VersionStore) -> None:
    r1 = client.get("/v1/identity")
    r2 = client.get("/v1/identity")
    assert r1.json()["public_key_pem"] == r2.json()["public_key_pem"]


# ── GET /v1/federations ───────────────────────────────────────────────────────


def test_list_federations_empty(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.get("/v1/federations")
    assert r.status_code == 200
    assert r.json() == []


def test_list_federations_after_create(client: TestClient, federation: dict) -> None:
    r = client.get("/v1/federations")
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert "test-fed" in names


# ── POST /v1/federations ──────────────────────────────────────────────────────


def test_create_federation_success(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.post("/v1/federations", json={"name": "alpha"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "alpha"
    assert data["is_founder"] is True
    assert data["member_count"] == 1


def test_create_federation_duplicate_name_returns_409(client: TestClient, federation: dict) -> None:
    r = client.post("/v1/federations", json={"name": "test-fed"})
    assert r.status_code == 409


# ── GET /v1/federations/{id}/members ──────────────────────────────────────────


def test_list_members_success(client: TestClient, federation: dict) -> None:
    fed_id = federation["id"]
    r = client.get(f"/v1/federations/{fed_id}/members")
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 1
    assert "public_key" in members[0]


def test_list_members_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.get("/v1/federations/no-such-id/members")
    assert r.status_code == 404


# ── DELETE /v1/federations/{id}/members/{mid} ─────────────────────────────────


def test_eject_member_federation_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.delete("/v1/federations/no-such-id/members/mid")
    assert r.status_code == 404


def test_eject_member_not_founder_returns_403(
    client: TestClient, store: VersionStore, vault: Path
) -> None:
    """Simulate a non-founder server attempting eject."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Overwrite the founding_key_enc with a *different* server's key so is_founder=False
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationOrm  # noqa: PLC0415

    pub2, _priv2 = generate_key_pair()
    enc_key = store._fed_enc_key
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()
    # Clear the cached _orm_to_federation result
    r = client.delete(f"/v1/federations/{fed.id}/members/some-member-id")
    assert r.status_code == 403


def test_eject_member_not_found(client: TestClient, federation: dict) -> None:
    fed_id = federation["id"]
    r = client.delete(f"/v1/federations/{fed_id}/members/no-such-member")
    assert r.status_code == 404


def test_eject_member_success(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    r = client.delete(f"/v1/federations/{fed.id}/members/{founding_member.id}")
    assert r.status_code == 204


# ── POST /v1/federations/{id}/join ────────────────────────────────────────────


def test_join_federation_success(client: TestClient, federation: dict, store: VersionStore) -> None:
    fed_id = federation["id"]
    mock_c = _make_http_mock(
        {"ok": True, "message": "joined", "members": [], "federation_name": "test-fed"}
    )
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(
            f"/v1/federations/{fed_id}/join",
            json={"founding_url": "http://founder.example/v1/federate"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_join_federation_server_error_returns_502(client: TestClient, federation: dict) -> None:
    # Third party imports:
    import httpx  # noqa: PLC0415

    fed_id = federation["id"]
    mock_c = _make_http_error_mock(httpx.ConnectError("refused"))
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(
            f"/v1/federations/{fed_id}/join",
            json={"founding_url": "http://founder.example/v1/federate"},
        )
    assert r.status_code == 502


def test_join_federation_not_ok_response(client: TestClient, federation: dict) -> None:
    fed_id = federation["id"]
    mock_c = _make_http_mock({"ok": False, "message": "rejected"})
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(
            f"/v1/federations/{fed_id}/join",
            json={"founding_url": "http://founder.example/v1/federate"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is False


# ── POST /v1/federations/{id}/leave ──────────────────────────────────────────


def test_leave_federation_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.post("/v1/federations/no-such-id/leave")
    assert r.status_code == 404


def test_leave_federation_success(client: TestClient, federation: dict) -> None:
    fed_id = federation["id"]
    mock_c = _make_http_mock({})
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(f"/v1/federations/{fed_id}/leave")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_leave_federation_notify_error_still_ok(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Add a second member with a federate_url so the leave notification fires
    pub2, _priv2 = generate_key_pair()
    store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate")
    # Third party imports:
    import httpx  # noqa: PLC0415

    mock_c = _make_http_error_mock(httpx.ConnectError("refused"))
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(f"/v1/federations/{fed.id}/leave")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "errors" in data["message"] or "left" in data["message"]


# ── POST /v1/federations/{id}/sync ────────────────────────────────────────────


def test_sync_federation_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    r = client.post("/v1/federations/no-such-id/sync")
    assert r.status_code == 404


def test_sync_federation_is_founder_returns_400(client: TestClient, federation: dict) -> None:
    fed_id = federation["id"]
    r = client.post(f"/v1/federations/{fed_id}/sync")
    assert r.status_code == 400


def test_sync_federation_no_founder_url_returns_400(
    client: TestClient, store: VersionStore
) -> None:
    """Non-founder federation with no founder URL should return 400."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Overwrite founding_key_enc so is_founder=False, but leave member URL empty
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationOrm  # noqa: PLC0415

    pub2, _priv2 = generate_key_pair()
    enc_key = store._fed_enc_key
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()
    r = client.post(f"/v1/federations/{fed.id}/sync")
    assert r.status_code == 400


def test_sync_federation_http_error_returns_502(client: TestClient, store: VersionStore) -> None:
    """Non-founder with valid founder URL but httpx error → 502."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Add a second server as founder; make the local server non-founder
    pub2, priv2 = generate_key_pair()
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationMemberOrm, FederationOrm  # noqa: PLC0415

    enc_key = store._fed_enc_key
    # Override founding_key to pub2 so local server is NOT founder
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()
    # Add the founder as a member with a URL
    store.add_federation_member(fed.id, pub2, "http://founder.example/v1/federate")
    # Third party imports:
    import httpx  # noqa: PLC0415

    mock_c = _make_http_error_mock(httpx.ConnectError("refused"))
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(f"/v1/federations/{fed.id}/sync")
    assert r.status_code == 502


# ── POST /v1/federate (inbound protocol) ──────────────────────────────────────


def test_federate_invalid_signature_returns_401(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    pub2, _priv2 = generate_key_pair()
    r = client.post(
        "/v1/federate",
        json={
            "federation_id": "fed-id",
            "public_key": pub2,
            "federate_url": "http://peer.example/v1/federate",
            "is_accepted": True,
            "action": "join",
            "signature": "invalidsig",
        },
    )
    assert r.status_code == 401


def test_federate_join_action(client: TestClient, federation: dict, store: VersionStore) -> None:
    fed_id = federation["id"]
    pub2, priv2 = generate_key_pair()
    # Temporarily set the private key so sign works with pub2
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed_id,
        federate_url="http://peer.example/v1/federate",
        is_accepted=True,
        action="join",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["message"] == "joined"


def test_federate_join_federation_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    pub2, priv2 = generate_key_pair()
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id="no-such-id",
        federate_url="http://peer.example/v1/federate",
        is_accepted=True,
        action="join",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 404


def test_federate_leave_action(client: TestClient, federation: dict, store: VersionStore) -> None:
    fed_id = federation["id"]
    pub2, priv2 = generate_key_pair()
    # Add the member first
    store.add_federation_member(fed_id, pub2, "http://peer.example/v1/federate")
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed_id,
        federate_url="",
        is_accepted=False,
        action="leave",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "removed"


def test_federate_leave_nonexistent_member_ok(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    pub2, priv2 = generate_key_pair()
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed_id,
        federate_url="",
        is_accepted=False,
        action="leave",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200


def test_federate_notify_action(client: TestClient, federation: dict, store: VersionStore) -> None:
    fed_id = federation["id"]
    pub2, priv2 = generate_key_pair()
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed_id,
        federate_url="http://updated.example/v1/federate",
        is_accepted=True,
        action="notify",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "updated"


def test_federate_eject_action_by_founder(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    # The store's own identity is the founder
    identity = store.get_or_create_identity()
    pub2, priv2 = generate_key_pair()
    _ = store.add_federation_member(fed_id, pub2, "http://peer.example/v1/federate")
    # Sign as the founder (store's own private key)
    body = _signed_request(
        store,
        federation_id=fed_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="eject",
        target_key=pub2,
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "ejected"


def test_federate_eject_not_founder_returns_403(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    pub2, priv2 = generate_key_pair()
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed_id,
        federate_url="",
        is_accepted=False,
        action="eject",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 403


def test_federate_eject_federation_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    pub2, priv2 = generate_key_pair()
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id="no-such-id",
        federate_url="",
        is_accepted=False,
        action="eject",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 404


def test_federate_eject_self(client: TestClient, federation: dict, store: VersionStore) -> None:
    """Eject without target_key but sender is identity (self-eject path)."""
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    _ = store.get_member_by_key(fed_id, identity.public_key_pem)

    body = _signed_request(
        store,
        federation_id=fed_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="eject",
        target_key=None,
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200


def test_federate_unknown_action_returns_400(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    body = _signed_request(
        store,
        federation_id=fed_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=True,
        action="unknown-action",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 400


# ── POST /v1/federate/sync ────────────────────────────────────────────────────


def test_federate_sync_not_founder_returns_403(client: TestClient, store: VersionStore) -> None:
    """Sending a sync request to a non-founder server returns 403."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Override to make local server non-founder
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationOrm  # noqa: PLC0415

    pub2, priv2 = generate_key_pair()
    enc_key = store._fed_enc_key
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()

    members_json = json.dumps([])
    encrypted = encrypt_for(members_json.encode(), pub2)
    sig = sign_message(encrypted.encode(), priv2)
    r = client.post(
        "/v1/federate/sync",
        json={
            "federation_id": fed.id,
            "public_key": pub2,
            "encrypted_table": encrypted,
            "signature": sig,
        },
    )
    assert r.status_code == 403


def test_federate_sync_not_found(client: TestClient, store: VersionStore) -> None:
    store.get_or_create_identity()
    pub2, priv2 = generate_key_pair()
    members_json = json.dumps([])
    encrypted = encrypt_for(members_json.encode(), pub2)
    sig = sign_message(encrypted.encode(), priv2)
    r = client.post(
        "/v1/federate/sync",
        json={
            "federation_id": "no-such-id",
            "public_key": pub2,
            "encrypted_table": encrypted,
            "signature": sig,
        },
    )
    assert r.status_code == 404


def test_federate_sync_invalid_signature_returns_401(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    pub2, priv2 = generate_key_pair()
    members_json = json.dumps([])
    encrypted = encrypt_for(members_json.encode(), identity.public_key_pem)
    r = client.post(
        "/v1/federate/sync",
        json={
            "federation_id": fed_id,
            "public_key": pub2,
            "encrypted_table": encrypted,
            "signature": "bad-sig",
        },
    )
    assert r.status_code == 401


def test_federate_sync_decryption_failure_returns_400(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    fed_id = federation["id"]
    _ = store.get_or_create_identity()
    # Use a different key pair so the founder can't decrypt
    pub2, priv2 = generate_key_pair()
    # Encrypt with pub2 (founder can't decrypt since they have a different private key)
    encrypted = encrypt_for(b"not decryptable by founder", pub2)
    sig = sign_message(encrypted.encode(), priv2)
    r = client.post(
        "/v1/federate/sync",
        json={
            "federation_id": fed_id,
            "public_key": pub2,
            "encrypted_table": encrypted,
            "signature": sig,
        },
    )
    assert r.status_code == 400


def test_federate_sync_success(client: TestClient, federation: dict, store: VersionStore) -> None:
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    # Encrypt with the founder's (local server's) public key
    members_json = json.dumps([])
    encrypted = encrypt_for(members_json.encode(), identity.public_key_pem)
    pub2, priv2 = generate_key_pair()
    sig = sign_message(encrypted.encode(), priv2)
    r = client.post(
        "/v1/federate/sync",
        json={
            "federation_id": fed_id,
            "public_key": pub2,
            "encrypted_table": encrypted,
            "signature": sig,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "encrypted_table" in data
    assert "signature" in data


# ── Helper: sign with an arbitrary key pair ───────────────────────────────────


def _signed_request_with_key(
    priv_key: str,
    pub_key: str,
    federation_id: str,
    federate_url: str,
    is_accepted: bool,
    action: str,
    target_key: str | None = None,
) -> dict:
    """Build a FederateRequest body signed with *priv_key*."""
    # Standard library imports:
    import json as _json  # noqa: PLC0415

    # Local imports:
    from cantica.schemas.federate import FederateRequest  # noqa: PLC0415

    payload = FederateRequest(
        federation_id=federation_id,
        public_key=pub_key,
        federate_url=federate_url,
        is_accepted=is_accepted,
        action=action,
        target_key=target_key,
        signature="",
    )
    canonical = _json.dumps(payload.model_dump(exclude={"signature"}), sort_keys=True).encode()
    sig = sign_message(canonical, priv_key)
    return FederateRequest(
        federation_id=federation_id,
        public_key=pub_key,
        federate_url=federate_url,
        is_accepted=is_accepted,
        action=action,
        target_key=target_key,
        signature=sig,
    ).model_dump()


# ── eject_member: notify remaining members (lines 185-214, 219-220) ──────────


def test_eject_member_notifies_remaining_members(client: TestClient, store: VersionStore) -> None:
    """Ejecting a member when others remain triggers the notify loop + _send_federate."""
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    # Add member2 (will be notified — has a federate_url)
    pub2, _priv2 = generate_key_pair()
    _ = store.add_federation_member(fed.id, pub2, "http://peer2.example/v1/federate")
    # Add member3 (will be ejected)
    pub3, _priv3 = generate_key_pair()
    m3 = store.add_federation_member(fed.id, pub3, "")

    mock_c = _make_http_mock({})
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.delete(f"/v1/federations/{fed.id}/members/{m3.id}")
    assert r.status_code == 204


async def test_send_federate_helper(store: VersionStore) -> None:
    """_send_federate executes an async POST to the given URL (lines 219-220)."""
    # Local imports:
    from cantica.api.v1.endpoints.federate import _send_federate  # noqa: PLC0415
    from cantica.schemas.federate import FederateRequest  # noqa: PLC0415

    store.get_or_create_identity()
    fed, _ = store.create_federation("test-fed")
    payload = FederateRequest(
        federation_id=fed.id,
        public_key="pk",
        federate_url="http://peer.example/v1/federate",
        is_accepted=True,
        action="notify",
        signature="sig",
    )
    mock_c = _make_http_mock({})
    with patch("httpx.AsyncClient", return_value=mock_c):
        await _send_federate("http://peer.example/v1/federate", payload)
    mock_c.post.assert_awaited_once()


# ── join_federation: federation does not exist locally (lines 262-282) ───────


def test_join_federation_creates_local_placeholder(client: TestClient, store: VersionStore) -> None:
    """When ok=True and the federation is unknown locally, a placeholder is created."""
    store.get_or_create_identity()
    new_fed_id = "11111111-0000-0000-0000-000000000001"
    mock_c = _make_http_mock(
        {
            "ok": True,
            "message": "joined",
            "members": [],
            "federation_name": "remote-fed",
        }
    )
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(
            f"/v1/federations/{new_fed_id}/join",
            json={"founding_url": "http://founder.example/v1/federate"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── leave_federation: our membership not found (branch 338->340) ─────────────


def test_leave_federation_membership_not_found(client: TestClient, store: VersionStore) -> None:
    """Leave succeeds even when our own member record is absent."""
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    # Remove our own membership so get_member_by_key returns None
    store.remove_federation_member(founding_member.id)

    mock_c = _make_http_mock({})
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(f"/v1/federations/{fed.id}/leave")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── sync_federation: success path (lines 387-388) ────────────────────────────


def test_sync_federation_returns_encrypted_table(client: TestClient, store: VersionStore) -> None:
    """Non-founder sync succeeds and returns the canonical encrypted table."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Make local server a non-founder by changing the founding key
    pub2, priv2 = generate_key_pair()
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationOrm  # noqa: PLC0415

    enc_key = store._fed_enc_key
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()
    # Add pub2 as a member with URL so the founder endpoint is known
    store.add_federation_member(fed.id, pub2, "http://founder.example/v1/federate")

    mock_c = _make_http_mock({"encrypted_table": "dGVzdA==", "signature": "sig99"})
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.post(f"/v1/federations/{fed.id}/sync")
    assert r.status_code == 200
    data = r.json()
    assert data["encrypted_table"] == "dGVzdA=="
    assert data["signature"] == "sig99"


# ── federate eject: target_key given but member not found (branch 452->459) ──


def test_federate_eject_target_key_not_found_in_db(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    """Eject with target_key that matches no member: graceful no-op."""
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    body = _signed_request(
        store,
        federation_id=fed_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="eject",
        target_key="-----BEGIN PUBLIC KEY-----\nfake-key-not-in-db\n-----END PUBLIC KEY-----\n",
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "ejected"


# ── federate eject: no target_key and sender != our identity (454->459) ──────


def test_federate_eject_no_target_not_our_identity(client: TestClient, store: VersionStore) -> None:
    """Eject with no target_key from a sender that is not our local identity."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Replace founding key with pub2 so our identity is not the founder
    pub2, priv2 = generate_key_pair()
    # Third party imports:
    from sqlalchemy import update  # noqa: PLC0415

    # Local imports:
    from cantica.core.federation_crypto import encrypt_field  # noqa: PLC0415
    from cantica.orm.tables import FederationOrm  # noqa: PLC0415

    enc_key = store._fed_enc_key
    store.session.execute(
        update(FederationOrm)
        .where(FederationOrm.id == fed.id)
        .values(founding_key_enc=encrypt_field(pub2, enc_key))
    )
    store.session.commit()

    # pub2 (external founder) sends eject with no target_key
    body = _signed_request_with_key(
        priv_key=priv2,
        pub_key=pub2,
        federation_id=fed.id,
        federate_url="",
        is_accepted=False,
        action="eject",
        target_key=None,
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "ejected"


# ── federate eject: self-eject but already removed (branch 457->459) ─────────


def test_federate_eject_self_already_not_member(
    client: TestClient, federation: dict, store: VersionStore
) -> None:
    """Self-eject when identity is not in the member list: graceful no-op."""
    fed_id = federation["id"]
    identity = store.get_or_create_identity()
    # Remove our own membership before sending the self-eject
    our_member = store.get_member_by_key(fed_id, identity.public_key_pem)
    if our_member:
        store.remove_federation_member(our_member.id)

    body = _signed_request(
        store,
        federation_id=fed_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="eject",
        target_key=None,
    )
    r = client.post("/v1/federate", json=body)
    assert r.status_code == 200
    assert r.json()["message"] == "ejected"
