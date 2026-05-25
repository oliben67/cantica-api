# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import hashlib
import json
from datetime import UTC, datetime

# Third party imports:
import pytest
from fastapi.testclient import TestClient


def _ndjson(*records: dict) -> bytes:
    return b"".join((json.dumps(r) + "\n").encode() for r in records)


def _version_sha(
    content: str, author: str, message: str, created_at: str, parent_sha: str | None = None
) -> str:
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    commit_data = f"commit\n{content_sha}\n{parent_sha or ''}\n{author}\n{message}\n{created_at}"
    return hashlib.sha256(commit_data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Happy path — full import
# ---------------------------------------------------------------------------


def test_push_namespace_and_prompt(client: TestClient) -> None:
    data = _ndjson(
        {"type": "namespace", "name": "acme", "description": "ACME"},
        {
            "type": "prompt",
            "namespace": "acme",
            "name": "hello",
            "description": "",
            "tags": [],
            "model_hints": [],
            "license": "MIT",
            "visibility": "public",
            "variables": [],
        },
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 1  # prompt imported; namespace is "ignored"
    assert body["skipped"] == 0


def test_push_version_and_tag(client: TestClient) -> None:
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC).isoformat()
    sha = _version_sha("Hello", "alice", "Initial", created_at)
    data = _ndjson(
        {"type": "namespace", "name": "acme", "description": ""},
        {
            "type": "prompt",
            "namespace": "acme",
            "name": "hello",
            "description": "",
            "tags": [],
            "model_hints": [],
            "license": "MIT",
            "visibility": "public",
            "variables": [],
        },
        {
            "type": "version",
            "namespace": "acme",
            "name": "hello",
            "sha": sha,
            "content": "Hello",
            "message": "Initial",
            "author": "alice",
            "branch": "main",
            "parent_sha": None,
            "created_at": created_at,
            "variables": [],
        },
        {"type": "tag", "namespace": "acme", "name": "hello", "tag_name": "v1.0", "sha": sha},
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] >= 3  # prompt + version + tag


def test_push_skips_existing_prompt(client: TestClient, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    store = VersionStore(vault)
    store.create_prompt("acme", "hello")
    store.close()

    data = _ndjson(
        {"type": "namespace", "name": "acme", "description": ""},
        {
            "type": "prompt",
            "namespace": "acme",
            "name": "hello",
            "description": "",
            "tags": [],
            "model_hints": [],
            "license": "MIT",
            "visibility": "public",
            "variables": [],
        },
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    assert resp.json()["skipped"] == 1


def test_push_skips_existing_version(client: TestClient, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    store = VersionStore(vault)
    prompt = store.create_prompt("acme", "hello")
    v = store.commit(prompt.id, "Hi", "msg", "alice")
    store.close()

    created_at = v.created_at.isoformat()
    data = _ndjson(
        {"type": "namespace", "name": "acme", "description": ""},
        {
            "type": "prompt",
            "namespace": "acme",
            "name": "hello",
            "description": "",
            "tags": [],
            "model_hints": [],
            "license": "MIT",
            "visibility": "public",
            "variables": [],
        },
        {
            "type": "version",
            "namespace": "acme",
            "name": "hello",
            "sha": v.sha,
            "content": "Hi",
            "message": "msg",
            "author": "alice",
            "branch": "main",
            "parent_sha": None,
            "created_at": created_at,
            "variables": [],
        },
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    assert resp.json()["skipped"] >= 1


def test_push_checkpoint_and_unknown_type_ignored(client: TestClient) -> None:
    data = _ndjson(
        {"type": "checkpoint", "created_at": "2024-01-01T00:00:00+00:00"},
        {"type": "whatever", "data": "x"},
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    assert resp.json()["imported"] == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_push_invalid_json_returns_422(client: TestClient) -> None:
    data = b"not json\n"
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 422
    body = resp.json()
    assert "errors" in body["detail"]
    assert any("invalid JSON" in e for e in body["detail"]["errors"])


def test_push_empty_lines_ignored(client: TestClient) -> None:
    data = b"\n\n" + _ndjson({"type": "checkpoint", "created_at": "2024-01-01T00:00:00"})
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200


def test_push_version_missing_prompt_returns_422(client: TestClient) -> None:
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC).isoformat()
    sha = _version_sha("Hi", "alice", "msg", created_at)
    data = _ndjson(
        {
            "type": "version",
            "namespace": "missing",
            "name": "prompt",
            "sha": sha,
            "content": "Hi",
            "message": "msg",
            "author": "alice",
            "branch": "main",
            "parent_sha": None,
            "created_at": created_at,
            "variables": [],
        },
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 422


def test_push_tag_missing_prompt_skipped(client: TestClient) -> None:
    data = _ndjson(
        {"type": "tag", "namespace": "missing", "name": "prompt", "tag_name": "v1.0", "sha": "abc"},
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    assert resp.json()["skipped"] == 1


def test_push_tag_already_exists_skipped(client: TestClient, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    store = VersionStore(vault)
    prompt = store.create_prompt("acme", "hello")
    v = store.commit(prompt.id, "Hi", "msg", "alice")
    store.create_tag(prompt.id, "v1.0", v.sha)
    store.close()

    data = _ndjson(
        {"type": "namespace", "name": "acme", "description": ""},
        {"type": "tag", "namespace": "acme", "name": "hello", "tag_name": "v1.0", "sha": v.sha},
    )
    resp = client.post("/v1/push", content=data, headers={"Content-Type": "application/x-ndjson"})
    assert resp.status_code == 200
    assert resp.json()["skipped"] == 1
