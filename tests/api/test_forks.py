# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_fork_prompt(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/fork",
        json={"dest_namespace": "alice", "dest_name": "architect"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["source_slug"] == "osteck/architect"
    assert data["fork_slug"] == "alice/architect"


def test_fork_preserves_history(client: TestClient, seeded: dict, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    client.post(
        "/v1/prompts/osteck/architect/fork",
        json={"dest_namespace": "alice", "dest_name": "architect"},
    )
    store = VersionStore(vault)
    versions = store.log(store.get_prompt("alice", "architect").id)
    store.close()
    assert len(versions) == 2


def test_fork_source_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/fork",
        json={"dest_namespace": "alice", "dest_name": "copy"},
    )
    assert r.status_code == 404


def test_fork_dest_exists_returns_409(client: TestClient, seeded: dict) -> None:
    client.post(
        "/v1/prompts/osteck/architect/fork",
        json={"dest_namespace": "alice", "dest_name": "architect"},
    )
    r = client.post(
        "/v1/prompts/osteck/architect/fork",
        json={"dest_namespace": "alice", "dest_name": "architect"},
    )
    assert r.status_code == 409


def test_list_forks(client: TestClient, seeded: dict) -> None:
    client.post(
        "/v1/prompts/osteck/architect/fork",
        json={"dest_namespace": "alice", "dest_name": "architect"},
    )
    r = client.get("/v1/prompts/osteck/architect/forks")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["fork_slug"] == "alice/architect"


def test_list_forks_empty(client: TestClient, seeded: dict) -> None:
    r = client.get("/v1/prompts/osteck/architect/forks")
    assert r.status_code == 200
    assert r.json() == []


def test_list_forks_not_found(client: TestClient) -> None:
    r = client.get("/v1/prompts/nobody/nothing/forks")
    assert r.status_code == 404
