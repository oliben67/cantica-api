"""Tests for the lock file service and resolve_uri."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Third party imports:
import pytest

# Local imports:
from cantica.services.lock_file import LockEntry, LockFile, read_lock, write_lock
from cantica.services.version_store import VersionStore

# ------------------------------------------------------------------ #
# LockFile serialization                                               #
# ------------------------------------------------------------------ #


@pytest.fixture
def sample_lock() -> LockFile:
    now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    return LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://osteck/architect@v1.0",
                namespace="osteck",
                name="architect",
                ref="v1.0",
                sha="a" * 64,
                locked_at=now,
            )
        ],
    )


def test_write_and_read_lock_roundtrip(tmp_path: Path, sample_lock: LockFile) -> None:
    path = tmp_path / "cantica.lock"
    write_lock(sample_lock, path)
    loaded = read_lock(path)
    assert len(loaded.prompts) == 1
    assert loaded.prompts[0].uri == "cantica://osteck/architect@v1.0"
    assert loaded.prompts[0].sha == "a" * 64
    assert loaded.prompts[0].namespace == "osteck"
    assert loaded.cantica_version == "0.1"


def test_lock_file_is_valid_toml(tmp_path: Path, sample_lock: LockFile) -> None:
    # Standard library imports:
    import tomllib

    path = tmp_path / "cantica.lock"
    write_lock(sample_lock, path)
    data = tomllib.loads(path.read_text())
    assert "lock" in data
    assert "prompts" in data
    assert data["prompts"][0]["name"] == "architect"


def test_write_lock_multiple_entries(tmp_path: Path) -> None:
    now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    lock = LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://ns/a@v1",
                namespace="ns",
                name="a",
                ref="v1",
                sha="a" * 64,
                locked_at=now,
            ),
            LockEntry(
                uri="cantica://ns/b@v2",
                namespace="ns",
                name="b",
                ref="v2",
                sha="b" * 64,
                locked_at=now,
            ),
        ],
    )
    path = tmp_path / "cantica.lock"
    write_lock(lock, path)
    loaded = read_lock(path)
    assert len(loaded.prompts) == 2
    assert {e.name for e in loaded.prompts} == {"a", "b"}


def test_read_lock_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_lock(tmp_path / "nonexistent.lock")


# ------------------------------------------------------------------ #
# VersionStore.resolve_uri — local                                     #
# ------------------------------------------------------------------ #


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path)
    yield s
    s.close()


def test_resolve_uri_local_latest(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "test")
    v = store.commit(p.id, "content", "msg", "osteck")
    resolved = store.resolve_uri("cantica://osteck/test@latest")
    assert resolved.sha == v.sha


def test_resolve_uri_local_by_tag(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "test")
    v = store.commit(p.id, "content", "msg", "osteck")
    store.create_tag(p.id, "v1.0", v.sha)
    resolved = store.resolve_uri("cantica://osteck/test@v1.0")
    assert resolved.sha == v.sha


def test_resolve_uri_local_slug_form(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "test")
    v = store.commit(p.id, "content", "msg", "osteck")
    resolved = store.resolve_uri("osteck/test@latest")
    assert resolved.sha == v.sha


def test_resolve_uri_local_missing_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.resolve_uri("cantica://nobody/ghost@latest")


def test_resolve_uri_invalid_format_raises(store: VersionStore) -> None:
    with pytest.raises(ValueError):
        store.resolve_uri("cantica://")


# ------------------------------------------------------------------ #
# VersionStore.resolve_uri — remote (mocked httpx)                    #
# ------------------------------------------------------------------ #


def test_resolve_uri_remote_success(store: VersionStore) -> None:
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "sha": "a" * 64,
        "prompt_id": "pid",
        "branch": "main",
        "parent_sha": None,
        "message": "Initial",
        "author": "osteck",
        "content": "Hello",
        "variables": [],
        "created_at": "2026-05-24T12:00:00+00:00",
        "tags": [],
    }
    with patch("cantica.services.version_store.httpx.get", return_value=fake_response):
        version = store.resolve_uri("cantica://cantica.example.com/osteck/test@v1.0")
    assert version.sha == "a" * 64
    assert version.content == "Hello"


def test_resolve_uri_remote_not_found_raises(store: VersionStore) -> None:
    fake_response = MagicMock()
    fake_response.status_code = 404
    with patch("cantica.services.version_store.httpx.get", return_value=fake_response):
        with pytest.raises(KeyError):
            store.resolve_uri("cantica://cantica.example.com/nobody/ghost@latest")


def test_resolve_uri_remote_connection_error_raises(store: VersionStore) -> None:
    # Third party imports:
    import httpx as _httpx

    with patch(
        "cantica.services.version_store.httpx.get",
        side_effect=_httpx.RequestError("connection refused"),
    ):
        with pytest.raises(ConnectionError):
            store.resolve_uri("cantica://cantica.example.com/osteck/test@latest")


def test_resolve_uri_remote_url_override(store: VersionStore) -> None:
    """remote_url overrides the host from the URI."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "sha": "b" * 64,
        "prompt_id": "pid2",
        "branch": "main",
        "parent_sha": None,
        "message": "msg",
        "author": "a",
        "content": "c",
        "variables": [],
        "created_at": "2026-05-24T12:00:00+00:00",
        "tags": [],
    }
    with patch("cantica.services.version_store.httpx.get", return_value=fake_response) as mock_get:
        store.resolve_uri("cantica://some.host/ns/p@v1", remote_url="http://localhost:9000")
    called_url = mock_get.call_args[0][0]
    assert called_url.startswith("http://localhost:9000")
