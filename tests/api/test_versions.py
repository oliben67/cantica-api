# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_commit_version(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/versions",
        json={"content": "New content", "message": "Update", "author": "osteck"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "New content"
    assert data["message"] == "Update"


def test_list_versions(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/versions")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_versions_not_found(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/nothing/versions")
    assert r.status_code == 404


def test_get_version_at_latest(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/versions/latest")
    assert r.status_code == 200
    assert r.json()["message"] == "Senior bump"


def test_get_version_at_tag(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/versions/v1.0")
    assert r.status_code == 200
    assert r.json()["message"] == "Initial"


def test_get_version_at_sha_prefix(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.get(f"/v1/prompts/osteck/architect/versions/{sha[:7]}")
    assert r.status_code == 200
    assert r.json()["sha"] == sha


def test_get_version_bad_ref(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/versions/nonexistent")
    assert r.status_code == 404


def test_commit_version_prompt_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/versions",
        json={"content": "x", "message": "m", "author": "a"},
    )
    assert r.status_code == 404


def test_version_parent_chain(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/versions")
    versions = r.json()
    assert versions[0]["parent_sha"] == versions[1]["sha"]
    assert versions[1]["parent_sha"] is None


def test_import_version_with_sha(client: TestClient, seeded: dict) -> None:
    v1 = seeded["v1"]
    # import v1 again with its SHA — should be idempotent (already exists)
    r = client.post(
        "/v1/prompts/osteck/architect/versions",
        json={
            "content": v1.content,
            "message": v1.message,
            "author": v1.author,
            "branch": v1.branch,
            "sha": v1.sha,
            "parent_sha": v1.parent_sha,
            "created_at": v1.created_at.isoformat(),
        },
    )
    assert r.status_code == 201
    assert r.json()["sha"] == v1.sha


def test_import_version_sha_mismatch_returns_409(client: TestClient, seeded: dict) -> None:
    v1 = seeded["v1"]
    r = client.post(
        "/v1/prompts/osteck/architect/versions",
        json={
            "content": "tampered content",
            "message": v1.message,
            "author": v1.author,
            "branch": v1.branch,
            "sha": v1.sha,
            "parent_sha": v1.parent_sha,
            "created_at": v1.created_at.isoformat(),
        },
    )
    assert r.status_code == 409
