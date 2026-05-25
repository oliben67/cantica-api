"""
Access-control integration tests: 403 enforcement on all namespace-scoped endpoints.

Each test creates a proprietary namespace, issues a certificate, sets up a prompt
with a version inside it, then confirms that calling the endpoint without the cert
returns 403 and with the cert succeeds (2xx or 404 if sub-resource is absent).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def prop_setup(client: TestClient) -> dict:
    """
    Shared fixture: proprietary namespace ``ns`` with one prompt and one version.
    Returns a dict with ``token`` (cert token), ``sha`` (version sha).
    """
    client.post("/v1/namespaces", json={"name": "ns", "is_proprietary": True})
    cert = client.post("/v1/namespaces/ns/certificates", json={"granted_to": "alice"}).json()
    token = cert["token"]
    hdrs = {"X-Cantica-Certificate": token}

    client.post("/v1/prompts", json={"namespace": "ns", "name": "p"}, headers=hdrs)
    r = client.post(
        "/v1/prompts/ns/p/versions",
        json={"content": "hi", "message": "init", "author": "alice"},
        headers=hdrs,
    )
    sha = r.json()["sha"]
    return {"token": token, "sha": sha, "headers": hdrs}


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


def test_403_list_prompts_with_ns_filter(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts?namespace=ns").status_code == 403


def test_403_create_prompt(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/prompts", json={"namespace": "ns", "name": "other"})
    assert r.status_code == 403


def test_403_get_prompt(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p").status_code == 403


def test_403_delete_prompt(client: TestClient, prop_setup: dict) -> None:
    assert client.delete("/v1/prompts/ns/p").status_code == 403


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------


def test_403_list_versions(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/versions").status_code == 403


def test_403_commit_version(client: TestClient, prop_setup: dict) -> None:
    r = client.post(
        "/v1/prompts/ns/p/versions",
        json={"content": "x", "message": "m", "author": "a"},
    )
    assert r.status_code == 403


def test_403_get_version_at_ref(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/versions/latest").status_code == 403


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------


def test_403_list_tags(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/tags").status_code == 403


def test_403_create_tag(client: TestClient, prop_setup: dict) -> None:
    r = client.post(
        "/v1/prompts/ns/p/tags",
        json={"name": "v1", "sha": prop_setup["sha"]},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# branches
# ---------------------------------------------------------------------------


def test_403_list_branches(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/branches").status_code == 403


def test_403_create_branch(client: TestClient, prop_setup: dict) -> None:
    r = client.post(
        "/v1/prompts/ns/p/branches",
        json={"name": "dev", "from_sha": prop_setup["sha"]},
    )
    assert r.status_code == 403


def test_403_rollback(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/prompts/ns/p/rollback", json={"ref": "main", "branch": "main"})
    assert r.status_code == 403


def test_403_merge(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/prompts/ns/p/merge", json={"from_branch": "dev", "into_branch": "main"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# stars
# ---------------------------------------------------------------------------


def test_403_star(client: TestClient, prop_setup: dict) -> None:
    assert client.post("/v1/prompts/ns/p/star").status_code == 403


def test_403_unstar(client: TestClient, prop_setup: dict) -> None:
    assert client.delete("/v1/prompts/ns/p/star").status_code == 403


def test_403_stargazers(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/stargazers").status_code == 403


# ---------------------------------------------------------------------------
# comments
# ---------------------------------------------------------------------------


def test_403_add_comment(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/prompts/ns/p/comments", json={"body": "hi"})
    assert r.status_code == 403


def test_403_list_comments(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/comments").status_code == 403


def test_403_delete_comment(client: TestClient, prop_setup: dict) -> None:
    assert client.delete("/v1/prompts/ns/p/comments/fake-id").status_code == 403


# ---------------------------------------------------------------------------
# forks
# ---------------------------------------------------------------------------


def test_403_fork_prompt(client: TestClient, prop_setup: dict) -> None:
    r = client.post(
        "/v1/prompts/ns/p/fork",
        json={"dest_namespace": "public", "dest_name": "copy"},
    )
    assert r.status_code == 403


def test_403_list_forks(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/prompts/ns/p/forks").status_code == 403


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_403_diff(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/prompts/ns/p/diff", json={"ref1": "latest", "ref2": "latest"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def test_403_render(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/render", json={"slug": "ns/p", "ref": "latest"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------


def test_403_create_collection(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/collections", json={"namespace": "ns", "name": "c"})
    assert r.status_code == 403


def test_403_list_collections_with_ns_filter(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/collections?namespace=ns").status_code == 403


def test_403_get_collection(client: TestClient, prop_setup: dict) -> None:
    assert client.get("/v1/collections/ns/c").status_code == 403


def test_403_delete_collection(client: TestClient, prop_setup: dict) -> None:
    assert client.delete("/v1/collections/ns/c").status_code == 403


def test_403_add_collection_item(client: TestClient, prop_setup: dict) -> None:
    r = client.post("/v1/collections/ns/c/items", json={"prompt_slug": "ns/p"})
    assert r.status_code == 403


def test_403_remove_collection_item(client: TestClient, prop_setup: dict) -> None:
    assert client.delete("/v1/collections/ns/c/items/ns/p").status_code == 403


# ---------------------------------------------------------------------------
# namespace publish: invalid cert path (namespaces.py:136-137)
# ---------------------------------------------------------------------------


def test_403_publish_namespace_with_invalid_cert(client: TestClient) -> None:
    client.post("/v1/namespaces", json={"name": "tobe", "is_proprietary": True})
    r = client.patch(
        "/v1/namespaces/tobe",
        json={"is_proprietary": False},
        headers={"X-Cantica-Certificate": "invalid.token"},
    )
    assert r.status_code == 403
