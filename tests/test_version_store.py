# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest

# Local imports:
from cantica.models import VariableSchema
from cantica.services.version_store import VersionStore


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path)
    yield s
    s.close()


def test_create_prompt(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt", "A test prompt")
    assert p.namespace == "osteck"
    assert p.name == "my-prompt"
    assert p.slug == "osteck/my-prompt"


def test_create_namespace_idempotent(store: VersionStore) -> None:
    store.create_namespace("osteck")
    store.create_namespace("osteck")  # should not raise
    ns = store.get_namespace("osteck")
    assert ns is not None
    assert ns.name == "osteck"


def test_commit_returns_version(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "Hello world", "Initial commit", "osteck")
    assert v.content == "Hello world"
    assert v.message == "Initial commit"
    assert v.author == "osteck"
    assert v.branch == "main"
    assert v.parent_sha is None


def test_commit_parent_chain(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "v1", "First", "osteck")
    v2 = store.commit(p.id, "v2", "Second", "osteck")
    assert v2.parent_sha == v1.sha
    assert v1.parent_sha is None


def test_log_order(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "Hello world", "Initial commit", "osteck")
    v2 = store.commit(p.id, "Hello Python", "Update language", "osteck")

    log = store.log(p.id)
    assert len(log) == 2
    assert log[0].sha == v2.sha  # most recent first
    assert log[1].sha == v1.sha


def test_get_version_roundtrip(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "Content here", "msg", "author")
    retrieved = store.get_version(v.sha)
    assert retrieved is not None
    assert retrieved.content == "Content here"
    assert retrieved.sha == v.sha


def test_get_version_missing(store: VersionStore) -> None:
    assert store.get_version("deadbeef" * 8) is None


def test_tag_and_resolve(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "Content v1", "First commit", "osteck")
    store.create_tag(p.id, "v1.0", v1.sha)

    resolved = store.resolve("osteck", "my-prompt", "v1.0")
    assert resolved.sha == v1.sha


def test_tag_shows_in_version(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "Content", "First", "osteck")
    store.create_tag(p.id, "stable", v.sha)

    retrieved = store.get_version(v.sha)
    assert retrieved is not None
    assert "stable" in retrieved.tags


def test_resolve_latest(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    store.commit(p.id, "v1", "First", "osteck")
    v2 = store.commit(p.id, "v2", "Second", "osteck")

    resolved = store.resolve("osteck", "my-prompt", "latest")
    assert resolved.sha == v2.sha


def test_resolve_default_branch_name(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "content", "msg", "author")

    resolved = store.resolve("osteck", "my-prompt", "main")
    assert resolved.sha == v.sha


def test_resolve_sha_prefix(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "Content", "First", "osteck")

    resolved = store.resolve("osteck", "my-prompt", v.sha[:7])
    assert resolved.sha == v.sha


def test_branch_head_advances(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "Content", "First", "osteck")
    store.create_branch(p.id, "experimental", v1.sha)
    v2 = store.commit(p.id, "Experimental content", "Experiment", "osteck", branch="experimental")

    resolved = store.resolve("osteck", "my-prompt", "experimental")
    assert resolved.sha == v2.sha


def test_branch_isolation(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "Main content", "First", "osteck")
    store.create_branch(p.id, "feature", v1.sha)
    store.commit(p.id, "Feature content", "Feature commit", "osteck", branch="feature")
    store.commit(p.id, "More main", "Second main", "osteck")

    main_log = store.log(p.id, "main")
    feature_log = store.log(p.id, "feature")
    assert len(main_log) == 2
    assert len(feature_log) == 1


def test_list_branches(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "content", "msg", "author")
    store.create_branch(p.id, "dev", v.sha)

    branches = store.list_branches(p.id)
    names = {b.name for b in branches}
    assert "main" in names
    assert "dev" in names


def test_diff_unified(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v1 = store.commit(p.id, "Hello world", "First", "osteck")
    v2 = store.commit(p.id, "Hello Python", "Second", "osteck")

    diff = store.diff(v1.sha, v2.sha)
    assert "-Hello world" in diff
    assert "+Hello Python" in diff


def test_diff_missing_version_raises(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    v = store.commit(p.id, "content", "msg", "author")
    with pytest.raises(KeyError):
        store.diff(v.sha, "deadbeef" * 8)


def test_resolve_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError, match="osteck/missing"):
        store.resolve("osteck", "missing", "latest")


def test_resolve_bad_ref_raises(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    store.commit(p.id, "Content", "First", "osteck")
    with pytest.raises(KeyError, match="nonexistent"):
        store.resolve("osteck", "my-prompt", "nonexistent")


def test_commit_with_variables_roundtrip(store: VersionStore) -> None:
    p = store.create_prompt("osteck", "my-prompt")
    vars_ = [VariableSchema(name="language", default="Python", required=False)]
    v = store.commit(p.id, "Hello {{language}}", "First", "osteck", variables=vars_)

    retrieved = store.get_version(v.sha)
    assert retrieved is not None
    assert len(retrieved.variables) == 1
    assert retrieved.variables[0].name == "language"
    assert retrieved.variables[0].default == "Python"


def test_prompt_not_found_returns_none(store: VersionStore) -> None:
    assert store.get_prompt("nobody", "nothing") is None


# --------------------------------------------------------------------------- #
# search / filter                                                              #
# --------------------------------------------------------------------------- #


def test_list_prompts_filter_by_tag(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", tags=["python", "coding"])
    store.create_prompt("ns", "beta", tags=["rust"])
    results = store.list_prompts(tag="python")
    assert len(results) == 1
    assert results[0].name == "alpha"


def test_list_prompts_filter_by_model(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", model_hints=["gpt4"])
    store.create_prompt("ns", "beta", model_hints=["claude"])
    results = store.list_prompts(model="gpt4")
    assert len(results) == 1
    assert results[0].name == "alpha"


def test_list_prompts_filter_by_visibility(store: VersionStore) -> None:
    # Local imports:
    from cantica.models import Visibility

    store.create_prompt("ns", "pub", visibility=Visibility.public)
    store.create_prompt("ns", "priv", visibility=Visibility.private)
    results = store.list_prompts(visibility="private")
    assert len(results) == 1
    assert results[0].name == "priv"


def test_list_prompts_combined_filters(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", tags=["python"], model_hints=["gpt4"])
    store.create_prompt("ns", "beta", tags=["python"], model_hints=["claude"])
    results = store.list_prompts(tag="python", model="claude")
    assert len(results) == 1
    assert results[0].name == "beta"


def test_search_prompts_by_name(store: VersionStore) -> None:
    store.create_prompt("ns", "architect", description="Design systems")
    store.create_prompt("ns", "writer", description="Write copy")
    results = store.search_prompts("architect")
    assert len(results) == 1
    assert results[0].name == "architect"


def test_search_prompts_by_description(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", description="senior software engineer")
    store.create_prompt("ns", "beta", description="junior designer")
    results = store.search_prompts("senior")
    assert len(results) == 1
    assert results[0].name == "alpha"


def test_search_prompts_by_tag(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", tags=["python", "coding"])
    store.create_prompt("ns", "beta", tags=["rust"])
    results = store.search_prompts("python")
    assert len(results) == 1
    assert results[0].name == "alpha"


def test_search_prompts_no_results(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", description="something")
    results = store.search_prompts("xyzzy")
    assert results == []


def test_search_prompts_with_tag_filter(store: VersionStore) -> None:
    store.create_prompt("ns", "alpha", description="architect", tags=["python"])
    store.create_prompt("ns", "beta", description="architect", tags=["rust"])
    results = store.search_prompts("architect", tag="python")
    assert len(results) == 1
    assert results[0].name == "alpha"


def test_search_prompts_with_namespace_filter(store: VersionStore) -> None:
    store.create_prompt("alice", "alpha", description="architect")
    store.create_prompt("bob", "beta", description="architect")
    results = store.search_prompts("architect", namespace="alice")
    assert len(results) == 1
    assert results[0].namespace == "alice"


def test_fts_entry_removed_on_delete(store: VersionStore) -> None:
    p = store.create_prompt("ns", "todelete", description="unique phrase zorkblat")
    assert len(store.search_prompts("zorkblat")) == 1
    store.delete_prompt(p.id)
    assert store.search_prompts("zorkblat") == []


# ---------------------------------------------------------------------------
# Namespace access control — new coverage
# ---------------------------------------------------------------------------


def test_verify_cert_token_revoked_returns_none(store: VersionStore) -> None:
    store.create_namespace("prop", is_proprietary=True)
    cert = store.issue_certificate("prop", "alice")
    store.revoke_certificate(cert.id)
    # Revoked token must fail access check.
    with pytest.raises(PermissionError):
        store.check_namespace_access("prop", cert.token)


def test_encoded_namespace_commit_and_read(store: VersionStore) -> None:
    store.create_namespace("enc", encoded=True)
    p = store.create_prompt("enc", "secret")
    v = store.commit(p.id, "secret content", "init", "alice")
    fetched = store.get_version(v.sha)
    assert fetched is not None
    assert fetched.content == "secret content"


def test_encoded_namespace_import_version(store: VersionStore) -> None:
    store.create_namespace("enc2", encoded=True)
    p = store.create_prompt("enc2", "imp")
    # First commit to get a sha to use as parent
    v1 = store.commit(p.id, "v1 content", "first", "alice")
    # Standard library imports:
    from datetime import UTC, datetime

    v2 = store.import_version(
        p.id,
        v1.sha,  # re-import same sha — idempotent
        "v1 content",
        "first",
        "alice",
        "main",
        None,
        v1.created_at,
    )
    assert v2 is not None


def test_search_excludes_encoded_namespace(store: VersionStore) -> None:
    store.create_namespace("enc3", encoded=True)
    store.create_prompt("enc3", "hidden", description="secretterm")
    results = store.search_prompts("secretterm")
    assert results == []


def test_search_excludes_proprietary_without_cert(store: VersionStore) -> None:
    store.create_namespace("prop2", is_proprietary=True)
    store.create_prompt("prop2", "private", description="proprietaryterm")
    results = store.search_prompts("proprietaryterm")
    assert results == []


def test_search_includes_proprietary_with_valid_cert(store: VersionStore) -> None:
    store.create_namespace("prop3", is_proprietary=True)
    store.create_prompt("prop3", "certified", description="certifiedterm")
    cert = store.issue_certificate("prop3", "alice")
    results = store.search_prompts("certifiedterm", cert_token=cert.token)
    assert len(results) == 1
    assert results[0].name == "certified"


def test_search_with_invalid_cert_token_excludes_proprietary(store: VersionStore) -> None:
    store.create_namespace("prop4", is_proprietary=True)
    store.create_prompt("prop4", "blocked", description="invalidterm")
    # An invalid cert_token still excludes proprietary namespaces (payload=None branch).
    results = store.search_prompts("invalidterm", cert_token="bad.token")
    assert results == []


def test_create_encoded_namespace_generates_key(store: VersionStore) -> None:
    # Third party imports:
    from sqlalchemy import select

    # Local imports:
    from cantica.orm.tables import NamespaceOrm

    ns = store.create_namespace("enc", encoded=True)
    assert ns.encoded is True
    row = store.session.execute(select(NamespaceOrm).where(NamespaceOrm.name == "enc")).scalar_one()
    assert row.encryption_key is not None and len(row.encryption_key) == 64


def test_update_namespace_not_found_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.update_namespace("missing", description="x")


def test_update_namespace_no_changes(store: VersionStore) -> None:
    store.create_namespace("acme")
    ns = store.update_namespace("acme")
    assert ns.name == "acme"


def test_commit_and_get_version_in_encoded_namespace(store: VersionStore) -> None:
    store.create_namespace("enc", encoded=True)
    p = store.create_prompt("enc", "secret")
    v = store.commit(p.id, "secret content", "Initial", "alice")
    assert v.content == "secret content"
    retrieved = store.get_version(v.sha)
    assert retrieved is not None
    assert retrieved.content == "secret content"


def test_import_version_in_encoded_namespace(store: VersionStore) -> None:
    # Standard library imports:
    import hashlib
    from datetime import UTC, datetime

    store.create_namespace("enc", encoded=True)
    p = store.create_prompt("enc", "secret")
    content = "imported secret"
    author = "alice"
    message = "msg"
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    commit_data = f"commit\n{content_sha}\n\n{author}\n{message}\n{created_at.isoformat()}"
    sha = hashlib.sha256(commit_data.encode()).hexdigest()

    v = store.import_version(p.id, sha, content, message, author, "main", None, created_at)
    assert v.content == content


def test_verify_cert_revoked_raises_permission_error(store: VersionStore) -> None:
    store.create_namespace("priv", is_proprietary=True)
    cert = store.issue_certificate("priv", "alice")
    store.revoke_certificate(cert.id)
    with pytest.raises(PermissionError):
        store.check_namespace_access("priv", cert.token)
