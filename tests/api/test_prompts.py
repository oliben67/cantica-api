# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_create_prompt(client: TestClient) -> None:
    r = client.post("/v1/prompts", json={"namespace": "osteck", "name": "my-prompt"})
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "osteck/my-prompt"
    assert data["namespace"] == "osteck"


def test_create_prompt_duplicate(client: TestClient) -> None:
    payload = {"namespace": "osteck", "name": "dup"}
    client.post("/v1/prompts", json=payload)
    r = client.post("/v1/prompts", json=payload)
    assert r.status_code == 409


def test_get_prompt(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect")
    assert r.status_code == 200
    assert r.json()["name"] == "architect"


def test_get_prompt_not_found(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/nothing")
    assert r.status_code == 404


def test_list_prompts_empty(client: TestClient) -> None:
    r = client.get("/v1/prompts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_prompts(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_prompts_namespace_filter(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts?namespace=osteck")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/v1/prompts?namespace=nobody")
    assert r.status_code == 200
    assert r.json() == []


def test_delete_prompt(client: TestClient, seeded: dict) -> None:
    r = client.delete("/v1/prompts/osteck/architect")
    assert r.status_code == 204

    r = client.get("/v1/prompts/osteck/architect")
    assert r.status_code == 404


def test_delete_prompt_not_found(client: TestClient) -> None:
    r = client.delete("/v1/prompts/nobody/nothing")
    assert r.status_code == 404
