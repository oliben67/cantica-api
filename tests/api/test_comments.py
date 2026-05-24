# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def prompt(client: TestClient) -> dict:
    r = client.post("/v1/prompts", json={"namespace": "ns", "name": "p"})
    assert r.status_code == 201
    return r.json()


def test_add_comment_returns_201(client: TestClient, prompt: dict) -> None:
    r = client.post("/v1/prompts/ns/p/comments", json={"body": "Nice prompt!"})
    assert r.status_code == 201
    data = r.json()
    assert data["body"] == "Nice prompt!"
    assert data["author"] == "local"
    assert data["version_sha"] is None


def test_add_comment_with_version_sha(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.post(
        "/v1/prompts/osteck/architect/comments",
        json={"body": "First version comment", "version_sha": sha},
    )
    assert r.status_code == 201
    assert r.json()["version_sha"] == sha


def test_add_comment_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.post("/v1/prompts/nobody/ghost/comments", json={"body": "Hello"})
    assert r.status_code == 404


def test_list_comments(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/comments", json={"body": "First"})
    client.post("/v1/prompts/ns/p/comments", json={"body": "Second"})
    r = client.get("/v1/prompts/ns/p/comments")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_comments_filter_by_version(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    client.post("/v1/prompts/osteck/architect/comments", json={"body": "On v1", "version_sha": sha})
    client.post("/v1/prompts/osteck/architect/comments", json={"body": "General"})
    r = client.get("/v1/prompts/osteck/architect/comments", params={"version_sha": sha})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["body"] == "On v1"


def test_list_comments_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/ghost/comments")
    assert r.status_code == 404


def test_delete_comment(client: TestClient, prompt: dict) -> None:
    add = client.post("/v1/prompts/ns/p/comments", json={"body": "delete me"})
    cid = add.json()["id"]
    r = client.delete(f"/v1/prompts/ns/p/comments/{cid}")
    assert r.status_code == 204
    remaining = client.get("/v1/prompts/ns/p/comments").json()
    assert all(c["id"] != cid for c in remaining)


def test_list_comments_empty(client: TestClient, prompt: dict) -> None:
    r = client.get("/v1/prompts/ns/p/comments")
    assert r.status_code == 200
    assert r.json() == []
