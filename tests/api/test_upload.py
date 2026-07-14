"""Tests for POST /v1/upload (PyPI-style prompt upload)."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from io import BytesIO
from pathlib import Path

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_current_user, get_settings, get_store
from cantica.config import Settings
from cantica.main import create_app
from cantica.models.user import Role, User
from cantica.services.version_store import VersionStore


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def store(vault: Path) -> VersionStore:
    s = VersionStore(vault)
    yield s
    s.close()


@pytest.fixture
def write_user() -> User:
    return User(id="u1", username="uploader", roles=[Role.user])


@pytest.fixture
def client(vault: Path, store: VersionStore, write_user: User) -> TestClient:
    app = create_app()
    settings = Settings(vault_path=vault, auth_enabled=False)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_current_user] = lambda: write_user
    with TestClient(app) as c:
        yield c


# ── POST /v1/upload ───────────────────────────────────────────────────────────


def test_upload_creates_new_prompt(client: TestClient, store: VersionStore):
    r = client.post(
        "/v1/upload",
        data={
            "namespace": "acme",
            "name": "greeter",
            "content": "Hello {{ name }}",
            "message": "Initial upload",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["author"] == "uploader"
    assert data["message"] == "Initial upload"
    assert store.get_prompt("acme", "greeter") is not None


def test_upload_existing_prompt_adds_version(client: TestClient, store: VersionStore):
    client.post("/v1/upload", data={"namespace": "acme", "name": "bot", "content": "v1"})
    r = client.post("/v1/upload", data={"namespace": "acme", "name": "bot", "content": "v2"})
    assert r.status_code == 201
    prompt = store.get_prompt("acme", "bot")
    assert prompt is not None


def test_upload_via_file(client: TestClient):
    r = client.post(
        "/v1/upload",
        data={
            "namespace": "acme",
            "name": "from-file",
        },
        files={"content_file": ("prompt.txt", BytesIO(b"File content here"), "text/plain")},
    )
    assert r.status_code == 201
    assert "sha" in r.json()


def test_upload_no_content_returns_422(client: TestClient):
    r = client.post("/v1/upload", data={"namespace": "acme", "name": "empty"})
    assert r.status_code == 422


def test_upload_with_tags_and_description(client: TestClient, store: VersionStore):
    r = client.post(
        "/v1/upload",
        data={
            "namespace": "acme",
            "name": "tagged",
            "content": "prompt body",
            "description": "A tagged prompt",
            "tags": "ai,gpt,llm",
        },
    )
    assert r.status_code == 201
    prompt = store.get_prompt("acme", "tagged")
    assert prompt is not None
    assert prompt.description == "A tagged prompt"
    assert "ai" in prompt.tags


def test_upload_requires_write_role():
    """Anonymous (readonly) user gets 403."""
    # Standard library imports:
    from pathlib import Path  # noqa: PLC0415

    # Third party imports:
    import pytest  # noqa: PLC0415

    app = create_app()
    anon = User(id="anon", username="anon", roles=[Role.readonly])
    app.dependency_overrides[get_current_user] = lambda: anon
    with TestClient(app) as c:
        r = c.post(
            "/v1/upload",
            data={
                "namespace": "x",
                "name": "y",
                "content": "z",
            },
        )
    assert r.status_code == 403
