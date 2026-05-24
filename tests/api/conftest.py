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
from cantica.services.version_store import VersionStore


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def client(vault: Path) -> TestClient:
    app = create_app()

    test_settings = Settings(vault_path=vault, auth_enabled=False)
    test_store = VersionStore(vault)

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_store] = lambda: test_store

    with TestClient(app) as c:
        yield c

    test_store.close()


@pytest.fixture
def seeded(client: TestClient, vault: Path) -> dict:
    """Create a prompt with two versions and return their metadata."""
    store = VersionStore(vault)
    prompt = store.create_prompt("osteck", "architect", "A test prompt")
    v1 = store.commit(prompt.id, "You are an architect.", "Initial", "osteck")
    v2 = store.commit(prompt.id, "You are a senior architect.", "Senior bump", "osteck")
    store.create_tag(prompt.id, "v1.0", v1.sha)
    store.close()
    return {"prompt": prompt, "v1": v1, "v2": v2}
