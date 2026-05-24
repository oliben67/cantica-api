# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from unittest.mock import MagicMock, patch

# Third party imports:
from fastapi.testclient import TestClient


def test_resolve_local_uri(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.post("/v1/resolve", json={"uri": f"cantica://osteck/architect@{sha[:7]}"})
    assert r.status_code == 200
    assert r.json()["sha"] == sha


def test_resolve_slug_form(client: TestClient, seeded: dict) -> None:
    r = client.post("/v1/resolve", json={"uri": "osteck/architect@latest"})
    assert r.status_code == 200
    assert r.json()["sha"] == seeded["v2"].sha


def test_resolve_missing_prompt_returns_404(client: TestClient) -> None:
    r = client.post("/v1/resolve", json={"uri": "cantica://nobody/ghost@latest"})
    assert r.status_code == 404


def test_resolve_invalid_uri_returns_422(client: TestClient) -> None:
    r = client.post("/v1/resolve", json={"uri": "cantica://"})
    assert r.status_code == 422


def test_resolve_remote_connection_error_returns_502(client: TestClient) -> None:
    # Third party imports:
    import httpx as _httpx

    with patch(
        "cantica.services.version_store.httpx.get",
        side_effect=_httpx.RequestError("refused"),
    ):
        r = client.post("/v1/resolve", json={"uri": "cantica://remote.host/ns/p@latest"})
    assert r.status_code == 502


def test_resolve_remote_not_found_returns_404(client: TestClient) -> None:
    fake = MagicMock()
    fake.status_code = 404
    with patch("cantica.services.version_store.httpx.get", return_value=fake):
        r = client.post("/v1/resolve", json={"uri": "cantica://remote.host/ns/p@latest"})
    assert r.status_code == 404
