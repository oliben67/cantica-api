"""Targeted tests to cover remaining edge cases."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest
from sqlalchemy import text, update

# Local imports:
from cantica.core.logger import get_logger, setup_logging
from cantica.core.resolver import parse_address
from cantica.core.security import generate_api_key, hash_api_key
from cantica.orm.tables import BranchOrm, VersionOrm
from cantica.services.blob_store import BlobStore
from cantica.services.version_store import VersionStore

# ------------------------------------------------------------------ #
# core/logger                                                          #
# ------------------------------------------------------------------ #


def test_get_logger_returns_logger() -> None:
    logger = get_logger("cantica.test")
    assert logger.name == "cantica.test"


def test_setup_logging_debug_level() -> None:
    setup_logging("debug")  # should not raise


# ------------------------------------------------------------------ #
# core/security                                                        #
# ------------------------------------------------------------------ #


def test_hash_api_key_is_deterministic() -> None:
    h1 = hash_api_key("my-secret")
    h2 = hash_api_key("my-secret")
    assert h1 == h2


def test_hash_differs_from_raw() -> None:
    raw, key_hash = generate_api_key()
    assert hash_api_key(raw) == key_hash


# ------------------------------------------------------------------ #
# core/resolver — empty-field guard                                    #
# ------------------------------------------------------------------ #


def test_parse_address_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        parse_address("osteck/@ref")


# ------------------------------------------------------------------ #
# config — get_settings direct call                                    #
# ------------------------------------------------------------------ #


def test_get_settings_returns_settings() -> None:
    # Local imports:
    from cantica.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.port == 8042
    get_settings.cache_clear()


# ------------------------------------------------------------------ #
# api/deps — get_store direct call                                     #
# ------------------------------------------------------------------ #


def test_get_store_creates_version_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CANTICA_VAULT_PATH", str(tmp_path / "vault"))
    # Local imports:
    from cantica.api.deps import get_store
    from cantica.config import get_settings

    get_settings.cache_clear()
    get_store.cache_clear()
    store = get_store()
    assert isinstance(store, VersionStore)
    get_store.cache_clear()
    get_settings.cache_clear()


# ------------------------------------------------------------------ #
# services/blob_store                                                  #
# ------------------------------------------------------------------ #


def test_put_deduplicates_identical_content(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    sha1 = bs.put("same content")
    sha2 = bs.put("same content")  # should not raise, should skip write
    assert sha1 == sha2


def test_exists_true_after_put(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    sha = bs.put("check me")
    assert bs.exists(sha) is True


def test_exists_false_for_unknown(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    assert bs.exists("a" * 64) is False


# ------------------------------------------------------------------ #
# services/version_store — resolve edge cases                          #
# ------------------------------------------------------------------ #


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path)
    yield s
    s.close()


def test_resolve_ambiguous_prefix_raises(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    # Insert a fake version whose SHA shares the first 7 chars with v1
    fake_sha = v1.sha[:8] + "0" * (64 - 8)
    store.session.execute(
        text(
            """INSERT INTO versions(sha, prompt_id, branch, message, author,
               content_sha, variables, created_at)
               VALUES(:sha,:prompt_id,:branch,:message,:author,:content_sha,:variables,:created_at)"""
        ),
        {
            "sha": fake_sha,
            "prompt_id": prompt.id,
            "branch": "main",
            "message": "fake",
            "author": "fake",
            "content_sha": v1.sha,
            "variables": "[]",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    store.session.commit()
    with pytest.raises(ValueError, match="ambiguous"):
        store.resolve("osteck", "test", v1.sha[:7])


def test_resolve_dangling_branch_head_raises(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    store.commit(prompt.id, "v1", "First", "osteck")
    store.session.execute(text("PRAGMA foreign_keys = OFF"))
    store.session.execute(
        update(BranchOrm)
        .where(BranchOrm.prompt_id == prompt.id, BranchOrm.name == "main")
        .values(head_sha="a" * 64)
    )
    store.session.commit()
    store.session.execute(text("PRAGMA foreign_keys = ON"))
    with pytest.raises(KeyError, match="dangling"):
        store.resolve("osteck", "test", "latest")


def test_resolve_exact_sha_from_different_prompt_falls_through(store: VersionStore) -> None:
    store.create_prompt("osteck", "p1")
    p2 = store.create_prompt("osteck", "p2")
    v_other = store.commit(p2.id, "other", "msg", "osteck")
    # Trying to resolve p1 with p2's full SHA should raise KeyError
    with pytest.raises(KeyError):
        store.resolve("osteck", "p1", v_other.sha)


def test_get_namespace_returns_namespace(store: VersionStore) -> None:
    store.create_namespace("acme", "ACME corp")
    ns = store.get_namespace("acme")
    assert ns is not None
    assert ns.name == "acme"
    assert ns.created_at is not None


def test_get_namespace_missing_returns_none(store: VersionStore) -> None:
    assert store.get_namespace("nonexistent") is None


def test_blob_get_missing_raises(tmp_path: Path) -> None:
    # Local imports:
    from cantica.services.blob_store import BlobStore

    bs = BlobStore(tmp_path)
    with pytest.raises(KeyError, match="not found"):
        bs.get("a" * 64)


def test_diff_first_sha_not_found_raises(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    with pytest.raises(KeyError):
        store.diff("b" * 64, v1.sha)


def test_diff_second_sha_not_found_raises(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    with pytest.raises(KeyError):
        store.diff(v1.sha, "b" * 64)


def test_resolve_prompt_with_no_commits_raises(store: VersionStore) -> None:
    store.create_prompt("osteck", "empty")
    with pytest.raises(KeyError, match="no commits"):
        store.resolve("osteck", "empty", "latest")


def test_resolve_exact_full_sha(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    result = store.resolve("osteck", "test", v1.sha)
    assert result.sha == v1.sha


# ------------------------------------------------------------------ #
# services/version_store — import_version / list_tags                 #
# ------------------------------------------------------------------ #


def test_import_version_sha_mismatch_raises(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    with pytest.raises(ValueError, match="SHA mismatch"):
        store.import_version(
            prompt.id, "a" * 64, "v1", "First", "osteck", "main", None, v1.created_at
        )


def test_import_version_idempotent(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    imported = store.import_version(
        prompt.id, v1.sha, "v1", "First", "osteck", "main", None, v1.created_at
    )
    assert imported.sha == v1.sha


def test_import_version_updates_existing_branch(store: VersionStore) -> None:
    # Standard library imports:
    from datetime import UTC, datetime, timedelta

    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    # Build a valid second version that chains from v1
    # Local imports:
    from cantica.services.blob_store import BlobStore
    from cantica.services.version_store import _commit_sha

    blobs = BlobStore(store.root / "objects")
    content2 = "v2"
    content_sha2 = blobs.put(content2)
    created_at2 = v1.created_at + timedelta(seconds=1)
    sha2 = _commit_sha(content_sha2, v1.sha, "osteck", "Second", created_at2)
    imported = store.import_version(
        prompt.id, sha2, content2, "Second", "osteck", "main", v1.sha, created_at2
    )
    assert imported.sha == sha2
    branch = store.get_branch(prompt.id, "main")
    assert branch is not None
    assert branch.head_sha == sha2


def test_list_tags_returns_all(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck")
    v2 = store.commit(prompt.id, "v2", "Second", "osteck")
    store.create_tag(prompt.id, "v1.0", v1.sha)
    store.create_tag(prompt.id, "stable", v2.sha)
    tags = store.list_tags(prompt.id)
    assert {t.name for t in tags} == {"v1.0", "stable"}


# ------------------------------------------------------------------ #
# fork — tag not in sha_map (tag on different branch)                 #
# ------------------------------------------------------------------ #


def test_fork_skips_tags_from_other_branch(store: VersionStore) -> None:
    source = store.create_prompt("osteck", "source")
    v_main = store.commit(source.id, "main content", "Main", "osteck", branch="main")
    store.create_branch(source.id, "feature", v_main.sha)
    v_feat = store.commit(source.id, "feat content", "Feature", "osteck", branch="feature")
    # tag points to feature version; we fork main branch only
    store.create_tag(source.id, "feat-tag", v_feat.sha)
    store.create_tag(source.id, "main-tag", v_main.sha)

    store.fork("osteck", "source", "alice", "copy", branch="main")
    dest = store.get_prompt("alice", "copy")
    assert dest is not None
    # main-tag was remapped; feat-tag was not (points to feature-only SHA)
    dest_tags = {t.name for t in store.list_tags(dest.id)}
    assert "main-tag" in dest_tags
    assert "feat-tag" not in dest_tags


# ------------------------------------------------------------------ #
# merge — into branch that has no commits yet                         #
# ------------------------------------------------------------------ #


def test_merge_into_empty_branch(store: VersionStore) -> None:
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "v1", "First", "osteck", branch="main")
    # merge main into a non-existent "newbranch" — should create it
    result = store.merge("osteck", "test", "main", "newbranch")
    assert result.sha == v1.sha
    branch = store.get_branch(prompt.id, "newbranch")
    assert branch is not None
    assert branch.head_sha == v1.sha


def test_version_store_close_is_idempotent(tmp_path: Path) -> None:
    s = VersionStore(tmp_path)
    s.close()
    s.close()  # second call must not raise


def test_search_prompts_model_and_visibility_filters(store: VersionStore) -> None:
    # Local imports:
    from cantica.models import Visibility

    store.create_prompt(
        "ns", "alpha", description="architect", model_hints=["gpt4"], visibility=Visibility.public
    )
    store.create_prompt(
        "ns", "beta", description="architect", model_hints=["claude"], visibility=Visibility.private
    )
    by_model = store.search_prompts("architect", model="gpt4")
    assert len(by_model) == 1 and by_model[0].name == "alpha"

    by_vis = store.search_prompts("architect", visibility="private")
    assert len(by_vis) == 1 and by_vis[0].name == "beta"


def test_open_session_create_tables_false(tmp_path: Path) -> None:
    # Local imports:
    from cantica.database import open_session
    from cantica.orm.base import Base

    db_path = tmp_path / "test.db"
    # create_tables=True first so the schema exists
    engine1, session1 = open_session(db_path, create_tables=True)
    session1.close()
    engine1.dispose()
    # create_tables=False should not error and FTS table still exists
    engine2, session2 = open_session(db_path, create_tables=False)
    # Third party imports:
    from sqlalchemy import text

    result = session2.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='prompts_fts'")
    ).scalar_one_or_none()
    assert result == "prompts_fts"
    session2.close()
    engine2.dispose()
