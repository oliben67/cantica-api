"""
API tests for namespace CRUD and certificate endpoints.

Covers:
- Namespace create / list / get / update
- Certificate issuance / listing / revocation
- 403 access control on all namespace-scoped endpoints
- Encoded namespace commit and retrieval (content round-trips)
- Search filtering by proprietary / encoded namespace
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proprietary(client: TestClient, ns: str = "secret") -> dict:
    """Create a proprietary namespace and return the response JSON."""
    r = client.post(
        "/v1/namespaces",
        json={"name": ns, "description": "private", "is_proprietary": True},
    )
    assert r.status_code == 201
    return r.json()


def _issue_cert(client: TestClient, ns: str = "secret") -> str:
    """Issue a certificate and return the token string."""
    r = client.post(
        f"/v1/namespaces/{ns}/certificates",
        json={"granted_to": "alice"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["token"] is not None
    return data["token"]


# ---------------------------------------------------------------------------
# Namespace CRUD
# ---------------------------------------------------------------------------


def test_create_public_namespace(client: TestClient) -> None:
    r = client.post("/v1/namespaces", json={"name": "pub", "description": "hello"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "pub"
    assert data["is_proprietary"] is False
    assert data["encoded"] is False


def test_create_proprietary_namespace(client: TestClient) -> None:
    data = _make_proprietary(client, "priv")
    assert data["is_proprietary"] is True


def test_create_encoded_namespace(client: TestClient) -> None:
    r = client.post("/v1/namespaces", json={"name": "enc", "encoded": True})
    assert r.status_code == 201
    assert r.json()["encoded"] is True


def test_list_namespaces(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "a"})
    client.post("/v1/namespaces", json={"name": "b"})
    r = client.get("/v1/namespaces")
    assert r.status_code == 200
    names = {ns["name"] for ns in r.json()}
    assert {"a", "b"}.issubset(names)


def test_get_namespace(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "myns"})
    r = client.get("/v1/namespaces/myns")
    assert r.status_code == 200
    assert r.json()["name"] == "myns"


def test_get_namespace_not_found(client: TestClient) -> None:
    r = client.get("/v1/namespaces/does-not-exist")
    assert r.status_code == 404


def test_update_namespace_description(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "upd"})
    r = client.patch("/v1/namespaces/upd", json={"description": "new desc"})
    assert r.status_code == 200
    assert r.json()["description"] == "new desc"


def test_update_namespace_not_found(client: TestClient) -> None:
    r = client.patch("/v1/namespaces/ghost", json={"description": "x"})
    assert r.status_code == 404


def test_publish_proprietary_namespace_requires_cert(client: TestClient) -> None:
    _make_proprietary(client, "tobe")
    r = client.patch("/v1/namespaces/tobe", json={"is_proprietary": False})
    assert r.status_code == 403


def test_publish_proprietary_namespace_with_cert(client: TestClient) -> None:
    _make_proprietary(client, "tobe2")
    token = _issue_cert(client, "tobe2")
    r = client.patch(
        "/v1/namespaces/tobe2",
        json={"is_proprietary": False},
        headers={"X-Cantica-Certificate": token},
    )
    assert r.status_code == 200
    assert r.json()["is_proprietary"] is False


# ---------------------------------------------------------------------------
# Certificate issuance / listing / revocation
# ---------------------------------------------------------------------------


def test_issue_certificate(client: TestClient) -> None:
    _make_proprietary(client, "certns")
    r = client.post("/v1/namespaces/certns/certificates", json={"granted_to": "bob"})
    assert r.status_code == 201
    data = r.json()
    assert data["granted_to"] == "bob"
    assert data["namespace"] == "certns"
    assert data["token"] is not None
    assert data["revoked"] is False


def test_issue_certificate_public_namespace(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "public-only"})
    r = client.post("/v1/namespaces/public-only/certificates", json={"granted_to": "bob"})
    assert r.status_code == 409


def test_issue_certificate_missing_namespace(client: TestClient) -> None:
    r = client.post("/v1/namespaces/unknown/certificates", json={"granted_to": "x"})
    assert r.status_code == 404


def test_list_certificates(client: TestClient) -> None:
    _make_proprietary(client, "listns")
    _issue_cert(client, "listns")
    _issue_cert(client, "listns")
    r = client.get("/v1/namespaces/listns/certificates")
    assert r.status_code == 200
    certs = r.json()
    assert len(certs) == 2
    # token is never returned in list responses
    assert all(c["token"] is None for c in certs)


def test_list_certificates_namespace_not_found(client: TestClient) -> None:
    r = client.get("/v1/namespaces/nope/certificates")
    assert r.status_code == 404


def test_revoke_certificate(client: TestClient) -> None:
    _make_proprietary(client, "revokens")
    r_issue = client.post(
        "/v1/namespaces/revokens/certificates", json={"granted_to": "carol"}
    )
    cert_id = r_issue.json()["id"]
    token = r_issue.json()["token"]

    # Revoke
    r = client.delete(f"/v1/namespaces/revokens/certificates/{cert_id}")
    assert r.status_code == 204

    # Revoked token is now rejected
    r = client.get("/v1/prompts/revokens/p", headers={"X-Cantica-Certificate": token})
    assert r.status_code in (403, 404)


def test_revoke_certificate_not_found(client: TestClient) -> None:
    _make_proprietary(client, "revokens2")
    r = client.delete("/v1/namespaces/revokens2/certificates/nonexistent-id")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Access control on all namespace-scoped endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def prop_ns_client(client: TestClient) -> tuple[TestClient, str]:
    """Returns (client, cert_token) for a proprietary namespace 'prop' with a prompt inside."""
    _make_proprietary(client, "prop")
    token = _issue_cert(client, "prop")
    # Create a prompt in the namespace using the cert
    r = client.post(
        "/v1/prompts",
        json={"namespace": "prop", "name": "secret-prompt"},
        headers={"X-Cantica-Certificate": token},
    )
    assert r.status_code == 201
    # Commit a version
    client.post(
        "/v1/prompts/prop/secret-prompt/versions",
        json={"content": "secret", "message": "init", "author": "alice"},
        headers={"X-Cantica-Certificate": token},
    )
    return client, token


def test_access_control_get_prompt(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    # Without cert → 403
    assert c.get("/v1/prompts/prop/secret-prompt").status_code == 403
    # With cert → 200
    assert (
        c.get("/v1/prompts/prop/secret-prompt", headers={"X-Cantica-Certificate": token}).status_code
        == 200
    )


def test_access_control_list_versions(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/versions").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/versions",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_get_version_at_ref(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/versions/latest").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/versions/latest",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_tags(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/tags").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/tags",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_branches(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/branches").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/branches",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_stargazers(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/stargazers").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/stargazers",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_comments(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/comments").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/comments",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_forks_list(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    assert c.get("/v1/prompts/prop/secret-prompt/forks").status_code == 403
    assert (
        c.get(
            "/v1/prompts/prop/secret-prompt/forks",
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_render(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    payload = {"slug": "prop/secret-prompt", "ref": "latest"}
    assert c.post("/v1/render", json=payload).status_code == 403
    assert (
        c.post(
            "/v1/render",
            json=payload,
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_diff(client: TestClient, prop_ns_client) -> None:
    c, token = prop_ns_client
    payload = {"ref1": "latest", "ref2": "latest"}
    assert c.post("/v1/prompts/prop/secret-prompt/diff", json=payload).status_code == 403
    assert (
        c.post(
            "/v1/prompts/prop/secret-prompt/diff",
            json=payload,
            headers={"X-Cantica-Certificate": token},
        ).status_code
        == 200
    )


def test_access_control_collection_create(client: TestClient) -> None:
    _make_proprietary(client, "collprop")
    r = client.post(
        "/v1/collections",
        json={"namespace": "collprop", "name": "my-coll"},
    )
    assert r.status_code == 403


def test_access_control_collection_list_with_ns_filter(client: TestClient) -> None:
    _make_proprietary(client, "collprop2")
    r = client.get("/v1/collections?namespace=collprop2")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Encoded namespace: content round-trip
# ---------------------------------------------------------------------------


def test_encoded_namespace_content_round_trip(client: TestClient) -> None:
    """Content stored in an encoded namespace must be returned decrypted."""
    r = client.post(
        "/v1/namespaces", json={"name": "enc-ns", "encoded": True, "is_proprietary": True}
    )
    assert r.status_code == 201
    token = _issue_cert(client, "enc-ns")
    headers = {"X-Cantica-Certificate": token}

    client.post(
        "/v1/prompts",
        json={"namespace": "enc-ns", "name": "secret-prompt"},
        headers=headers,
    )
    client.post(
        "/v1/prompts/enc-ns/secret-prompt/versions",
        json={"content": "Top secret content!", "message": "init", "author": "alice"},
        headers=headers,
    )

    r = client.get("/v1/prompts/enc-ns/secret-prompt/versions/latest", headers=headers)
    assert r.status_code == 200
    assert r.json()["content"] == "Top secret content!"


# ---------------------------------------------------------------------------
# Search filtering
# ---------------------------------------------------------------------------


def test_search_excludes_proprietary_without_cert(client: TestClient) -> None:
    """Proprietary namespace prompts must not appear in unauthenticated search."""
    _make_proprietary(client, "hidden")
    token = _issue_cert(client, "hidden")
    client.post(
        "/v1/prompts",
        json={"namespace": "hidden", "name": "hidden-prompt", "description": "supersecret"},
        headers={"X-Cantica-Certificate": token},
    )
    # Also create a public prompt with same keyword
    client.post(
        "/v1/namespaces", json={"name": "public"}
    )
    client.post(
        "/v1/prompts",
        json={"namespace": "public", "name": "public-prompt", "description": "supersecret"},
    )
    client.post(
        "/v1/prompts/public/public-prompt/versions",
        json={"content": "supersecret", "message": "init", "author": "user"},
    )

    r = client.get("/v1/prompts?q=supersecret")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "public-prompt" in names
    assert "hidden-prompt" not in names


def test_search_includes_proprietary_with_cert(client: TestClient) -> None:
    """Proprietary namespace prompts appear when valid cert is supplied."""
    _make_proprietary(client, "certified")
    token = _issue_cert(client, "certified")
    client.post(
        "/v1/prompts",
        json={"namespace": "certified", "name": "cert-prompt", "description": "uniqueterm"},
        headers={"X-Cantica-Certificate": token},
    )
    client.post(
        "/v1/prompts/certified/cert-prompt/versions",
        json={"content": "uniqueterm", "message": "init", "author": "user"},
        headers={"X-Cantica-Certificate": token},
    )

    r = client.get(
        "/v1/prompts?q=uniqueterm",
        headers={"X-Cantica-Certificate": token},
    )
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "cert-prompt" in names


def test_search_excludes_encoded_namespace(client: TestClient) -> None:
    """Encoded namespace prompts are always excluded from search results."""
    client.post("/v1/namespaces", json={"name": "enc-search", "encoded": True})
    # Directly create the prompt bypassing the access check (public encoded ns)
    client.post(
        "/v1/prompts",
        json={"namespace": "enc-search", "name": "enc-prompt", "description": "encodedterm"},
    )

    r = client.get("/v1/prompts?q=encodedterm")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "enc-prompt" not in names
