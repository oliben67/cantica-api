# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_list_namespaces_empty(client: TestClient) -> None:
    resp = client.get("/v1/namespaces")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_namespace(client: TestClient) -> None:
    resp = client.post("/v1/namespaces", json={"name": "acme", "description": "ACME corp"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "acme"
    assert data["is_proprietary"] is False
    assert data["encoded"] is False


def test_create_namespace_proprietary(client: TestClient) -> None:
    resp = client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    assert resp.status_code == 201
    assert resp.json()["is_proprietary"] is True


def test_create_namespace_idempotent(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "acme"})
    resp = client.post("/v1/namespaces", json={"name": "acme"})
    assert resp.status_code == 201


def test_get_namespace(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "acme"})
    resp = client.get("/v1/namespaces/acme")
    assert resp.status_code == 200
    assert resp.json()["name"] == "acme"


def test_get_namespace_not_found(client: TestClient) -> None:
    resp = client.get("/v1/namespaces/missing")
    assert resp.status_code == 404


def test_list_namespaces_after_create(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "acme"})
    client.post("/v1/namespaces", json={"name": "other"})
    resp = client.get("/v1/namespaces")
    names = [n["name"] for n in resp.json()]
    assert "acme" in names and "other" in names


def test_update_namespace_description(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "acme"})
    resp = client.patch("/v1/namespaces/acme", json={"description": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated"


def test_update_namespace_not_found(client: TestClient) -> None:
    resp = client.patch("/v1/namespaces/missing", json={"description": "X"})
    assert resp.status_code == 404


def test_update_namespace_make_proprietary(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "acme"})
    resp = client.patch("/v1/namespaces/acme", json={"is_proprietary": True})
    assert resp.status_code == 200
    assert resp.json()["is_proprietary"] is True


def test_update_namespace_publish_requires_cert(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    resp = client.patch("/v1/namespaces/priv", json={"is_proprietary": False})
    assert resp.status_code == 403


def test_update_namespace_publish_with_valid_cert(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    cert_resp = client.post("/v1/namespaces/priv/certificates", json={"granted_to": "alice"})
    token = cert_resp.json()["token"]
    resp = client.patch(
        "/v1/namespaces/priv",
        json={"is_proprietary": False},
        headers={"X-Cantica-Certificate": token},
    )
    assert resp.status_code == 200
    assert resp.json()["is_proprietary"] is False


def test_update_namespace_publish_with_invalid_cert(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    resp = client.patch(
        "/v1/namespaces/priv",
        json={"is_proprietary": False},
        headers={"X-Cantica-Certificate": "bad.token"},
    )
    assert resp.status_code == 403


def test_issue_certificate(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    resp = client.post("/v1/namespaces/priv/certificates", json={"granted_to": "alice"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["namespace"] == "priv"
    assert data["token"] is not None
    assert data["revoked"] is False


def test_issue_certificate_namespace_not_found(client: TestClient) -> None:
    resp = client.post("/v1/namespaces/missing/certificates", json={"granted_to": "alice"})
    assert resp.status_code == 404


def test_issue_certificate_public_namespace_conflict(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "pub"})
    resp = client.post("/v1/namespaces/pub/certificates", json={"granted_to": "alice"})
    assert resp.status_code == 409


def test_list_certificates(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    client.post("/v1/namespaces/priv/certificates", json={"granted_to": "alice"})
    client.post("/v1/namespaces/priv/certificates", json={"granted_to": "bob"})
    resp = client.get("/v1/namespaces/priv/certificates")
    assert resp.status_code == 200
    certs = resp.json()
    assert len(certs) == 2
    assert all(c["token"] is None for c in certs)


def test_list_certificates_namespace_not_found(client: TestClient) -> None:
    resp = client.get("/v1/namespaces/missing/certificates")
    assert resp.status_code == 404


def test_revoke_certificate(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    cert = client.post("/v1/namespaces/priv/certificates", json={"granted_to": "alice"}).json()
    resp = client.delete(f"/v1/namespaces/priv/certificates/{cert['id']}")
    assert resp.status_code == 204


def test_revoke_certificate_namespace_not_found(client: TestClient) -> None:
    resp = client.delete("/v1/namespaces/missing/certificates/fake-id")
    assert resp.status_code == 404


def test_revoke_certificate_not_found(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "priv", "is_proprietary": True})
    resp = client.delete("/v1/namespaces/priv/certificates/nonexistent-id")
    assert resp.status_code == 404


def test_update_namespace_store_error_returns_404(client: TestClient) -> None:
    """update_namespace raising KeyError maps to 404 (lines 136-137 in namespaces.py)."""
    # Standard library imports:
    from unittest.mock import patch  # noqa: PLC0415

    # Local imports:
    from cantica.services.version_store import VersionStore  # noqa: PLC0415

    client.post("/v1/namespaces", json={"name": "acme"})
    with patch.object(VersionStore, "update_namespace", side_effect=KeyError("not found")):
        resp = client.patch("/v1/namespaces/acme", json={"description": "X"})
    assert resp.status_code == 404
