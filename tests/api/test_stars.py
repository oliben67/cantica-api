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


def test_star_prompt_returns_201(client: TestClient, prompt: dict) -> None:
    r = client.post("/v1/prompts/ns/p/star")
    assert r.status_code == 201
    data = r.json()
    assert data["prompt_id"] == prompt["id"]
    assert data["namespace"] == "local"


def test_star_is_idempotent(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/star")
    r = client.post("/v1/prompts/ns/p/star")
    assert r.status_code == 201


def test_star_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.post("/v1/prompts/nobody/ghost/star")
    assert r.status_code == 404


def test_unstar_prompt(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/star")
    r = client.delete("/v1/prompts/ns/p/star")
    assert r.status_code == 204


def test_unstar_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.delete("/v1/prompts/nobody/ghost/star")
    assert r.status_code == 404


def test_list_stargazers(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/star")
    r = client.get("/v1/prompts/ns/p/stargazers")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["namespace"] == "local"


def test_list_stargazers_empty(client: TestClient, prompt: dict) -> None:
    r = client.get("/v1/prompts/ns/p/stargazers")
    assert r.status_code == 200
    assert r.json() == []


def test_list_stargazers_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/ghost/stargazers")
    assert r.status_code == 404


def test_star_count_increments(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/star")
    r = client.get("/v1/prompts/ns/p")
    assert r.json()["star_count"] == 1


def test_star_count_decrements_on_unstar(client: TestClient, prompt: dict) -> None:
    client.post("/v1/prompts/ns/p/star")
    client.delete("/v1/prompts/ns/p/star")
    r = client.get("/v1/prompts/ns/p")
    assert r.json()["star_count"] == 0
