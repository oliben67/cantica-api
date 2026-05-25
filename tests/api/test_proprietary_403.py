# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.services.version_store import VersionStore


@pytest.fixture
def prop_client(vault: Path) -> TestClient:
    """Client with a pre-created proprietary namespace and a seeded prompt."""
    # Local imports:
    from cantica.api.deps import get_settings, get_store
    from cantica.config import Settings
    from cantica.main import create_app

    app = create_app()
    test_settings = Settings(vault_path=vault, auth_enabled=False)
    test_store = VersionStore(vault)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_store] = lambda: test_store

    # Seed: proprietary namespace + a prompt + a version
    test_store.create_namespace("priv", is_proprietary=True)
    p = test_store.create_prompt("priv", "secret")
    test_store.commit(p.id, "secret content", "Initial", "alice")
    test_store.create_collection("priv", "my-col", "")
    test_store.add_to_collection("priv", "my-col", "priv/secret")

    with TestClient(app) as c:
        yield c

    test_store.close()


# ---------------------------------------------------------------------------
# Branches — all four handlers
# ---------------------------------------------------------------------------


def test_branches_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/branches")
    assert resp.status_code == 403


def test_branches_create_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/branches",
        json={"name": "dev", "from_sha": "a" * 64},
    )
    assert resp.status_code == 403


def test_branches_merge_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/merge",
        json={"from_branch": "main", "into_branch": "main"},
    )
    assert resp.status_code == 403


def test_branches_rollback_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/rollback",
        json={"ref": "latest", "branch": "main"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Collections — proprietary namespace
# ---------------------------------------------------------------------------


def test_collections_create_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/collections",
        json={"namespace": "priv", "name": "col2", "description": ""},
    )
    assert resp.status_code == 403


def test_collections_list_filtered_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/collections?namespace=priv")
    assert resp.status_code == 403


def test_collections_get_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/collections/priv/my-col")
    assert resp.status_code == 403


def test_collections_delete_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.delete("/v1/collections/priv/my-col")
    assert resp.status_code == 403


def test_collections_add_item_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/collections/priv/my-col/items",
        json={"prompt_slug": "priv/secret"},
    )
    assert resp.status_code == 403


def test_collections_remove_item_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.delete("/v1/collections/priv/my-col/items/priv/secret")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def test_comments_add_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/comments",
        json={"body": "Nice!"},
    )
    assert resp.status_code == 403


def test_comments_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/comments")
    assert resp.status_code == 403


def test_comments_delete_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.delete("/v1/prompts/priv/secret/comments/fake-id")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def test_diff_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/diff",
        json={"ref1": "latest", "ref2": "latest"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Forks
# ---------------------------------------------------------------------------


def test_forks_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/forks")
    assert resp.status_code == 403


def test_forks_create_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/fork",
        json={"dest_namespace": "priv", "dest_name": "fork"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Stars
# ---------------------------------------------------------------------------


def test_stars_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/stargazers")
    assert resp.status_code == 403


def test_stars_star_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post("/v1/prompts/priv/secret/star")
    assert resp.status_code == 403


def test_stars_unstar_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.delete("/v1/prompts/priv/secret/star")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_tags_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/tags")
    assert resp.status_code == 403


def test_tags_create_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/tags",
        json={"name": "v1.0", "sha": "a" * 64},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def test_versions_list_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/versions")
    assert resp.status_code == 403


def test_versions_commit_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/prompts/priv/secret/versions",
        json={"content": "hi", "message": "msg", "author": "alice"},
    )
    assert resp.status_code == 403


def test_versions_get_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret/versions/latest")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def test_prompts_list_filtered_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts?namespace=priv")
    assert resp.status_code == 403


def test_prompts_get_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.get("/v1/prompts/priv/secret")
    assert resp.status_code == 403


def test_prompts_delete_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.delete("/v1/prompts/priv/secret")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_render_proprietary_403(prop_client: TestClient) -> None:
    resp = prop_client.post(
        "/v1/render",
        json={"slug": "priv/secret", "ref": "latest"},
    )
    assert resp.status_code == 403
