# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_list_prompts_no_filters(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts")
    assert r.status_code == 200
    assert any(p["name"] == "architect" for p in r.json())


def test_list_prompts_filter_by_tag(client: TestClient) -> None:
    client.post("/v1/prompts", json={"namespace": "ns", "name": "alpha", "tags": ["python"]})
    client.post("/v1/prompts", json={"namespace": "ns", "name": "beta", "tags": ["rust"]})
    r = client.get("/v1/prompts", params={"tag": "python"})
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "alpha" in names
    assert "beta" not in names


def test_list_prompts_filter_by_model(client: TestClient) -> None:
    client.post("/v1/prompts", json={"namespace": "ns", "name": "m1", "model_hints": ["gpt4"]})
    client.post("/v1/prompts", json={"namespace": "ns", "name": "m2", "model_hints": ["claude"]})
    r = client.get("/v1/prompts", params={"model": "gpt4"})
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "m1" in names
    assert "m2" not in names


def test_list_prompts_filter_by_visibility(client: TestClient) -> None:
    client.post("/v1/prompts", json={"namespace": "ns", "name": "pub", "visibility": "public"})
    client.post("/v1/prompts", json={"namespace": "ns", "name": "priv", "visibility": "private"})
    r = client.get("/v1/prompts", params={"visibility": "private"})
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "priv" in names
    assert "pub" not in names


def test_search_prompts_fts(client: TestClient) -> None:
    client.post(
        "/v1/prompts", json={"namespace": "ns", "name": "finder", "description": "zorkblat unique"}
    )
    client.post(
        "/v1/prompts", json={"namespace": "ns", "name": "other", "description": "something else"}
    )
    r = client.get("/v1/prompts", params={"q": "zorkblat"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "finder"


def test_search_prompts_no_results(client: TestClient) -> None:
    r = client.get("/v1/prompts", params={"q": "xyzzy123"})
    assert r.status_code == 200
    assert r.json() == []


def test_search_with_tag_filter(client: TestClient) -> None:
    client.post(
        "/v1/prompts",
        json={"namespace": "ns", "name": "a", "description": "architect", "tags": ["python"]},
    )
    client.post(
        "/v1/prompts",
        json={"namespace": "ns", "name": "b", "description": "architect", "tags": ["rust"]},
    )
    r = client.get("/v1/prompts", params={"q": "architect", "tag": "rust"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "b"
