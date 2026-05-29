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


@pytest.fixture
def collection(client: TestClient) -> dict:
    r = client.post(
        "/v1/collections", json={"namespace": "ns", "name": "favs", "description": "My favs"}
    )
    assert r.status_code == 201
    return r.json()


def test_create_collection_returns_201(client: TestClient) -> None:
    r = client.post("/v1/collections", json={"namespace": "ns", "name": "c1"})
    assert r.status_code == 201
    data = r.json()
    assert data["namespace"] == "ns"
    assert data["name"] == "c1"


def test_create_collection_duplicate_returns_409(client: TestClient, collection: dict) -> None:
    r = client.post("/v1/collections", json={"namespace": "ns", "name": "favs"})
    assert r.status_code == 409


def test_list_collections_empty(client: TestClient) -> None:
    r = client.get("/v1/collections")
    assert r.status_code == 200
    assert r.json() == []


def test_list_collections_returns_all(client: TestClient, collection: dict) -> None:
    client.post("/v1/collections", json={"namespace": "ns", "name": "other"})
    r = client.get("/v1/collections")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_collections_filter_by_namespace(client: TestClient, collection: dict) -> None:
    client.post("/v1/collections", json={"namespace": "alice", "name": "hers"})
    r = client.get("/v1/collections", params={"namespace": "ns"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "favs" in names
    assert "hers" not in names


def test_get_collection_returns_detail(client: TestClient, collection: dict) -> None:
    r = client.get("/v1/collections/ns/favs")
    assert r.status_code == 200
    assert r.json()["description"] == "My favs"
    assert r.json()["items"] == []


def test_get_collection_not_found(client: TestClient) -> None:
    r = client.get("/v1/collections/nobody/nope")
    assert r.status_code == 404


def test_delete_collection(client: TestClient, collection: dict) -> None:
    r = client.delete("/v1/collections/ns/favs")
    assert r.status_code == 204
    assert client.get("/v1/collections/ns/favs").status_code == 404


def test_delete_collection_not_found(client: TestClient) -> None:
    r = client.delete("/v1/collections/nobody/nope")
    assert r.status_code == 404


def test_add_item_to_collection(client: TestClient, collection: dict, prompt: dict) -> None:
    r = client.post("/v1/collections/ns/favs/items", json={"prompt_slug": "ns/p"})
    assert r.status_code == 204
    detail = client.get("/v1/collections/ns/favs").json()
    assert len(detail["items"]) == 1
    assert detail["items"][0]["name"] == "p"


def test_add_item_idempotent(client: TestClient, collection: dict, prompt: dict) -> None:
    client.post("/v1/collections/ns/favs/items", json={"prompt_slug": "ns/p"})
    r = client.post("/v1/collections/ns/favs/items", json={"prompt_slug": "ns/p"})
    assert r.status_code == 204
    detail = client.get("/v1/collections/ns/favs").json()
    assert len(detail["items"]) == 1


def test_add_item_collection_not_found(client: TestClient, prompt: dict) -> None:
    r = client.post("/v1/collections/nobody/nope/items", json={"prompt_slug": "ns/p"})
    assert r.status_code == 404


def test_add_item_prompt_not_found(client: TestClient, collection: dict) -> None:
    r = client.post("/v1/collections/ns/favs/items", json={"prompt_slug": "nobody/ghost"})
    assert r.status_code == 404


def test_remove_item_from_collection(client: TestClient, collection: dict, prompt: dict) -> None:
    client.post("/v1/collections/ns/favs/items", json={"prompt_slug": "ns/p"})
    r = client.delete("/v1/collections/ns/favs/items/ns/p")
    assert r.status_code == 204
    detail = client.get("/v1/collections/ns/favs").json()
    assert detail["items"] == []


def test_remove_item_collection_not_found(client: TestClient) -> None:
    r = client.delete("/v1/collections/nobody/nope/items/ns/p")
    assert r.status_code == 404


def test_get_collection_items_store_error_returns_404(client: TestClient, collection: dict) -> None:
    """list_collection_items raising KeyError maps to 404 (lines 121-122 in collections.py)."""
    # Standard library imports:
    from unittest.mock import patch  # noqa: PLC0415

    # Local imports:
    from cantica.services.version_store import VersionStore  # noqa: PLC0415

    with patch.object(VersionStore, "list_collection_items", side_effect=KeyError("gone")):
        r = client.get("/v1/collections/ns/favs")
    assert r.status_code == 404
    assert "gone" in r.json()["detail"]
