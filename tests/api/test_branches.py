# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_list_branches(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/branches")
    assert r.status_code == 200
    names = {b["name"] for b in r.json()}
    assert "main" in names


def test_create_branch(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.post(
        "/v1/prompts/osteck/architect/branches",
        json={"name": "experimental", "from_sha": sha},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "experimental"
    assert r.json()["head_sha"] == sha


def test_create_branch_bad_sha(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/branches",
        json={"name": "broken", "from_sha": "deadbeef" * 8},
    )
    assert r.status_code == 404


def test_branches_not_found_prompt(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/nothing/branches")
    assert r.status_code == 404


def test_create_branch_prompt_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/branches",
        json={"name": "dev", "from_sha": "a" * 64},
    )
    assert r.status_code == 404
