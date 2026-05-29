# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from unittest.mock import AsyncMock, MagicMock, patch

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _add_peer(client: TestClient, name: str = "acme", url: str = "http://acme.example") -> dict:
    r = client.post("/v1/federation/peers", json={"name": name, "url": url})
    assert r.status_code == 201
    return r.json()


def _mock_http_client(prompts: list[dict]) -> tuple[MagicMock, MagicMock]:
    """Return (mock_client, mock_response) with .get wired up to return *prompts*."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=prompts)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client, mock_resp


def _mock_http_client_error(exc: Exception) -> MagicMock:
    """Return a mock client whose .get raises *exc*."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=exc)
    return mock_client


# ── Peer management ───────────────────────────────────────────────────────────


def test_list_peers_empty(client: TestClient) -> None:
    r = client.get("/v1/federation/peers")
    assert r.status_code == 200
    assert r.json() == []


def test_add_peer_returns_201(client: TestClient) -> None:
    r = client.post(
        "/v1/federation/peers",
        json={"name": "acme", "url": "http://acme.example", "api_key": "secret"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "acme"
    assert data["url"] == "http://acme.example"
    assert data["api_key"] == "secret"
    assert "id" in data
    assert "added_at" in data


def test_add_peer_without_api_key(client: TestClient) -> None:
    r = client.post("/v1/federation/peers", json={"name": "pub", "url": "http://pub.example"})
    assert r.status_code == 201
    assert r.json()["api_key"] is None


def test_list_peers_after_add(client: TestClient) -> None:
    _add_peer(client, "acme", "http://acme.example")
    _add_peer(client, "beta", "http://beta.example")
    r = client.get("/v1/federation/peers")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"acme", "beta"}


def test_remove_peer(client: TestClient) -> None:
    peer = _add_peer(client)
    r = client.delete(f"/v1/federation/peers/{peer['id']}")
    assert r.status_code == 204
    r2 = client.get("/v1/federation/peers")
    assert r2.json() == []


def test_remove_peer_not_found(client: TestClient) -> None:
    r = client.delete("/v1/federation/peers/no-such-id")
    assert r.status_code == 404


# ── Fan-out endpoints (mocked httpx) ──────────────────────────────────────────


def _mock_response(prompts: list[dict]):
    """Return a mock httpx Response-like object."""
    # Third party imports:
    import httpx

    return httpx.Response(200, json=prompts)


@pytest.fixture
def peer(client: TestClient) -> dict:
    return _add_peer(client, "acme", "http://acme.example")


def test_federated_search_no_peers_returns_empty(client: TestClient) -> None:
    r = client.get("/v1/federation/search?q=foo")
    assert r.status_code == 200
    assert r.json() == []


def test_federated_list_no_peers_returns_empty(client: TestClient) -> None:
    r = client.get("/v1/federation/prompts")
    assert r.status_code == 200
    assert r.json() == []


def test_federated_search_returns_peer_results(client: TestClient, peer: dict) -> None:
    fake_prompt = {
        "id": "abc", "namespace": "acme", "name": "greet", "description": "",
        "tags": [], "model_hints": [], "license": "MIT", "visibility": "public",
        "variables": [], "star_count": 0, "fork_count": 0, "default_branch": "main",
        "source": None, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
        "slug": "acme/greet",
    }
    mock_c, _ = _mock_http_client([fake_prompt])
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.get("/v1/federation/search?q=greet")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["peer_name"] == "acme"
    assert results[0]["error"] is None
    assert len(results[0]["prompts"]) == 1
    assert results[0]["prompts"][0]["name"] == "greet"


def test_federated_list_returns_peer_results(client: TestClient, peer: dict) -> None:
    fake_prompt = {
        "id": "xyz", "namespace": "acme", "name": "helper", "description": "",
        "tags": [], "model_hints": [], "license": "MIT", "visibility": "public",
        "variables": [], "star_count": 0, "fork_count": 0, "default_branch": "main",
        "source": None, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
        "slug": "acme/helper",
    }
    mock_c, _ = _mock_http_client([fake_prompt])
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.get("/v1/federation/prompts")
    assert r.status_code == 200
    results = r.json()
    assert results[0]["peer_name"] == "acme"
    assert len(results[0]["prompts"]) == 1


def test_federated_search_peer_error_is_captured(client: TestClient, peer: dict) -> None:
    # Third party imports:
    import httpx

    mock_c = _mock_http_client_error(httpx.ConnectError("refused"))
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.get("/v1/federation/search?q=foo")
    assert r.status_code == 200
    results = r.json()
    assert results[0]["error"] is not None
    assert results[0]["prompts"] == []


def test_federated_list_peer_error_is_captured(client: TestClient, peer: dict) -> None:
    # Third party imports:
    import httpx

    mock_c = _mock_http_client_error(httpx.ConnectError("refused"))
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.get("/v1/federation/prompts")
    assert r.status_code == 200
    assert r.json()[0]["error"] is not None


def test_federated_list_with_api_key_peer(client: TestClient) -> None:
    """Peer with api_key: X-API-Key header is included in the upstream request (line 61)."""
    r = client.post(
        "/v1/federation/peers",
        json={"name": "secured", "url": "http://secured.example", "api_key": "tok123"},
    )
    assert r.status_code == 201

    mock_c, _ = _mock_http_client([])
    with patch("httpx.AsyncClient", return_value=mock_c):
        r = client.get("/v1/federation/prompts")
    assert r.status_code == 200
    # Verify the X-API-Key header was forwarded to the upstream call
    call_kwargs = mock_c.get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("X-API-Key") == "tok123"
