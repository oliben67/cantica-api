# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_create_token(client: TestClient) -> None:
    r = client.post("/v1/tokens", json={"name": "my-token"})
    assert r.status_code == 201
    data = r.json()
    assert "key" in data
    assert len(data["key"]) > 20
    assert data["name"] == "my-token"


def test_list_tokens(client: TestClient) -> None:
    client.post("/v1/tokens", json={"name": "tok-a"})
    client.post("/v1/tokens", json={"name": "tok-b"})
    r = client.get("/v1/tokens")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert "tok-a" in names
    assert "tok-b" in names


def test_revoke_token(client: TestClient) -> None:
    r = client.post("/v1/tokens", json={"name": "temp"})
    token_id = r.json()["id"]

    r = client.delete(f"/v1/tokens/{token_id}")
    assert r.status_code == 204

    r = client.get("/v1/tokens")
    ids = {t["id"] for t in r.json()}
    assert token_id not in ids


def test_revoke_token_not_found(client: TestClient) -> None:
    r = client.delete("/v1/tokens/nonexistent-id")
    assert r.status_code == 404


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
