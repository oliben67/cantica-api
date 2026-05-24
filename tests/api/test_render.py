# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest
from fastapi.testclient import TestClient

# Local imports:
from cantica.api.deps import get_settings, get_store
from cantica.config import Settings
from cantica.main import create_app
from cantica.models import VariableSchema
from cantica.services.version_store import VersionStore


@pytest.fixture
def render_client(tmp_path: Path) -> TestClient:
    vault = tmp_path / "vault"
    app = create_app()
    store = VersionStore(vault)
    settings = Settings(vault_path=vault, auth_enabled=False)

    prompt = store.create_prompt("osteck", "greeter")
    store.commit(
        prompt.id,
        "Hello {{name}}, you are a {{role}}.",
        "Initial",
        "osteck",
        variables=[
            VariableSchema(name="name", required=True),
            VariableSchema(name="role", default="developer"),
        ],
    )

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c

    store.close()


def test_render_with_variables(render_client: TestClient) -> None:
    r = render_client.post(
        "/v1/render",
        json={"slug": "osteck/greeter", "variables": {"name": "Alice", "role": "architect"}},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Hello Alice, you are a architect."


def test_render_with_defaults(render_client: TestClient) -> None:
    r = render_client.post(
        "/v1/render",
        json={"slug": "osteck/greeter", "variables": {"name": "Bob"}},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Hello Bob, you are a developer."


def test_render_missing_required(render_client: TestClient) -> None:
    r = render_client.post("/v1/render", json={"slug": "osteck/greeter", "variables": {}})
    assert r.status_code == 422


def test_render_not_found(render_client: TestClient) -> None:
    r = render_client.post("/v1/render", json={"slug": "nobody/nothing"})
    assert r.status_code == 404


def test_render_bad_slug(render_client: TestClient) -> None:
    r = render_client.post("/v1/render", json={"slug": "no-slash"})
    assert r.status_code == 422
