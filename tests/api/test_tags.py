# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_list_tags(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/tags")
    assert r.status_code == 200
    tags = r.json()
    assert len(tags) == 1
    assert tags[0]["name"] == "v1.0"


def test_create_tag(client: TestClient, seeded: dict) -> None:
    sha = seeded["v2"].sha
    r = client.post(
        "/v1/prompts/osteck/architect/tags",
        json={"name": "stable", "sha": sha},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "stable"


def test_create_tag_bad_sha(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/tags",
        json={"name": "bad", "sha": "deadbeef" * 8},
    )
    assert r.status_code == 404


def test_tags_not_found_prompt(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/nothing/tags")
    assert r.status_code == 404


def test_create_tag_prompt_not_found(client: TestClient) -> None:
    r = client.post("/v1/prompts/nobody/nothing/tags", json={"name": "v1", "sha": "a" * 64})
    assert r.status_code == 404
