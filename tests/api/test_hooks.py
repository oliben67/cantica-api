# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from unittest.mock import patch

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# ── discovery ──────────────────────────────────────────────────────────────── #


def test_discovery_endpoint(client: TestClient) -> None:
    r = client.get("/.well-known/cantica.json")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "0.1"
    assert "/v1" in data["api_url"]
    assert "webhooks_url" in data


# ── CRUD ───────────────────────────────────────────────────────────────────── #


def test_create_hook_returns_201(client: TestClient) -> None:
    r = client.post(
        "/v1/hooks",
        json={"url": "https://example.com/webhook", "secret": "s3cr3t"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["url"] == "https://example.com/webhook"
    assert data["events"] == ["version.created"]
    assert data["namespace"] is None
    assert "id" in data


def test_create_hook_with_namespace_filter(client: TestClient) -> None:
    r = client.post(
        "/v1/hooks",
        json={"url": "https://example.com/hook2", "secret": "abc", "namespace": "osteck"},
    )
    assert r.status_code == 201
    assert r.json()["namespace"] == "osteck"


def test_list_hooks_empty(client: TestClient) -> None:
    r = client.get("/v1/hooks")
    assert r.status_code == 200
    assert r.json() == []


def test_list_hooks_returns_created(client: TestClient) -> None:
    client.post("/v1/hooks", json={"url": "https://a.example/h", "secret": "x"})
    client.post("/v1/hooks", json={"url": "https://b.example/h", "secret": "y"})
    r = client.get("/v1/hooks")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_delete_hook(client: TestClient) -> None:
    created = client.post("/v1/hooks", json={"url": "https://del.example/h", "secret": "s"}).json()
    r = client.delete(f"/v1/hooks/{created['id']}")
    assert r.status_code == 204
    assert client.get("/v1/hooks").json() == []


def test_delete_hook_not_found(client: TestClient) -> None:
    r = client.delete("/v1/hooks/nonexistent-id")
    assert r.status_code == 404


# ── webhook delivery ───────────────────────────────────────────────────────── #


@pytest.fixture
def prompt_with_hook(client: TestClient) -> dict:
    """Create a prompt + webhook; return prompt data."""
    client.post("/v1/hooks", json={"url": "https://recv.example/h", "secret": "s3cr3t"})
    r = client.post("/v1/prompts", json={"namespace": "ns", "name": "p"})
    assert r.status_code == 201
    return r.json()


def test_commit_fires_webhook(client: TestClient, prompt_with_hook: dict) -> None:
    with patch("cantica.services.version_store.httpx.post") as mock_post:
        r = client.post(
            "/v1/prompts/ns/p/versions",
            json={"content": "hello", "message": "m", "author": "a"},
        )
        assert r.status_code == 201
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["headers"]["X-Cantica-Event"] == "version.created"
    assert call_kwargs.kwargs["headers"]["X-Cantica-Signature"].startswith("sha256=")


def test_webhook_skipped_when_event_not_subscribed(client: TestClient) -> None:
    client.post(
        "/v1/hooks", json={"url": "https://r.example/h", "secret": "s", "events": ["other.event"]}
    )
    client.post("/v1/prompts", json={"namespace": "ns2", "name": "q"})
    with patch("cantica.services.version_store.httpx.post") as mock_post:
        client.post(
            "/v1/prompts/ns2/q/versions", json={"content": "hi", "message": "m", "author": "a"}
        )
    mock_post.assert_not_called()


def test_webhook_skipped_when_namespace_mismatch(client: TestClient) -> None:
    client.post(
        "/v1/hooks", json={"url": "https://r.example/h", "secret": "s", "namespace": "other"}
    )
    client.post("/v1/prompts", json={"namespace": "ns3", "name": "r"})
    with patch("cantica.services.version_store.httpx.post") as mock_post:
        client.post(
            "/v1/prompts/ns3/r/versions", json={"content": "hi", "message": "m", "author": "a"}
        )
    mock_post.assert_not_called()


def test_webhook_delivery_failure_is_silenced(client: TestClient, prompt_with_hook: dict) -> None:
    with patch("cantica.services.version_store.httpx.post", side_effect=OSError("network error")):
        r = client.post(
            "/v1/prompts/ns/p/versions",
            json={"content": "hi2", "message": "m", "author": "a"},
        )
    assert r.status_code == 201
