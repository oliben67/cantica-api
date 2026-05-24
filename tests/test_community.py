"""Tests for stars, comments, and collections in VersionStore."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest

# Local imports:
from cantica.services.version_store import VersionStore


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def prompt(store: VersionStore):
    return store.create_prompt("ns", "p")


# ------------------------------------------------------------------ #
# Stars                                                                #
# ------------------------------------------------------------------ #


def test_star_prompt_returns_star(store: VersionStore, prompt) -> None:
    star = store.star_prompt("ns", "p", "alice")
    assert star.namespace == "alice"
    assert star.prompt_id == prompt.id


def test_star_increments_count(store: VersionStore, prompt) -> None:
    store.star_prompt("ns", "p", "alice")
    p = store.get_prompt("ns", "p")
    assert p is not None
    assert p.star_count == 1


def test_star_is_idempotent(store: VersionStore, prompt) -> None:
    store.star_prompt("ns", "p", "alice")
    store.star_prompt("ns", "p", "alice")
    p = store.get_prompt("ns", "p")
    assert p is not None
    assert p.star_count == 1


def test_star_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.star_prompt("nobody", "ghost", "alice")


def test_unstar_removes_star(store: VersionStore, prompt) -> None:
    store.star_prompt("ns", "p", "alice")
    removed = store.unstar_prompt("ns", "p", "alice")
    assert removed is True
    p = store.get_prompt("ns", "p")
    assert p is not None
    assert p.star_count == 0


def test_unstar_returns_false_when_not_starred(store: VersionStore, prompt) -> None:
    assert store.unstar_prompt("ns", "p", "alice") is False


def test_unstar_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.unstar_prompt("nobody", "ghost", "alice")


def test_list_stargazers(store: VersionStore, prompt) -> None:
    store.star_prompt("ns", "p", "alice")
    store.star_prompt("ns", "p", "bob")
    stars = store.list_stargazers("ns", "p")
    namespaces = {s.namespace for s in stars}
    assert namespaces == {"alice", "bob"}


def test_list_stargazers_empty(store: VersionStore, prompt) -> None:
    assert store.list_stargazers("ns", "p") == []


def test_list_stargazers_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.list_stargazers("nobody", "ghost")


# ------------------------------------------------------------------ #
# Comments                                                             #
# ------------------------------------------------------------------ #


def test_add_comment_returns_comment(store: VersionStore, prompt) -> None:
    c = store.add_comment("ns", "p", "Great prompt!", "alice")
    assert c.body == "Great prompt!"
    assert c.author == "alice"
    assert c.version_sha is None


def test_add_comment_with_version_sha(store: VersionStore, prompt) -> None:
    v = store.commit(prompt.id, "content", "msg", "alice")
    c = store.add_comment("ns", "p", "On v1", "alice", v.sha)
    assert c.version_sha == v.sha


def test_add_comment_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.add_comment("nobody", "ghost", "hello", "alice")


def test_list_comments_returns_all(store: VersionStore, prompt) -> None:
    store.add_comment("ns", "p", "First", "alice")
    store.add_comment("ns", "p", "Second", "bob")
    comments = store.list_comments("ns", "p")
    assert len(comments) == 2


def test_list_comments_filter_by_version(store: VersionStore, prompt) -> None:
    v = store.commit(prompt.id, "content", "msg", "alice")
    store.add_comment("ns", "p", "On version", "alice", v.sha)
    store.add_comment("ns", "p", "General", "alice")
    filtered = store.list_comments("ns", "p", v.sha)
    assert len(filtered) == 1
    assert filtered[0].body == "On version"


def test_list_comments_missing_prompt_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.list_comments("nobody", "ghost")


def test_delete_comment_returns_true(store: VersionStore, prompt) -> None:
    c = store.add_comment("ns", "p", "to delete", "alice")
    assert store.delete_comment(c.id) is True
    assert store.list_comments("ns", "p") == []


def test_delete_comment_returns_false_when_missing(store: VersionStore) -> None:
    assert store.delete_comment("nonexistent-id") is False


# ------------------------------------------------------------------ #
# Collections                                                          #
# ------------------------------------------------------------------ #


def test_create_collection(store: VersionStore) -> None:
    c = store.create_collection("ns", "favs", "My favourites")
    assert c.namespace == "ns"
    assert c.name == "favs"
    assert c.description == "My favourites"


def test_create_collection_duplicate_raises(store: VersionStore) -> None:
    store.create_collection("ns", "favs")
    with pytest.raises(ValueError, match="already exists"):
        store.create_collection("ns", "favs")


def test_get_collection_returns_collection(store: VersionStore) -> None:
    store.create_collection("ns", "favs")
    c = store.get_collection("ns", "favs")
    assert c is not None
    assert c.name == "favs"


def test_get_collection_missing_returns_none(store: VersionStore) -> None:
    assert store.get_collection("nobody", "nope") is None


def test_list_collections(store: VersionStore) -> None:
    store.create_collection("ns", "a")
    store.create_collection("ns", "b")
    colls = store.list_collections("ns")
    assert {c.name for c in colls} == {"a", "b"}


def test_list_collections_no_namespace_filter(store: VersionStore) -> None:
    store.create_collection("alice", "x")
    store.create_collection("bob", "y")
    assert len(store.list_collections()) == 2


def test_delete_collection_returns_true(store: VersionStore) -> None:
    store.create_collection("ns", "favs")
    assert store.delete_collection("ns", "favs") is True
    assert store.get_collection("ns", "favs") is None


def test_delete_collection_returns_false_when_missing(store: VersionStore) -> None:
    assert store.delete_collection("nobody", "nope") is False


def test_add_to_collection(store: VersionStore, prompt) -> None:
    store.create_collection("ns", "favs")
    store.add_to_collection("ns", "favs", "ns/p")
    items = store.list_collection_items("ns", "favs")
    assert len(items) == 1
    assert items[0].name == "p"


def test_add_to_collection_idempotent(store: VersionStore, prompt) -> None:
    store.create_collection("ns", "favs")
    store.add_to_collection("ns", "favs", "ns/p")
    store.add_to_collection("ns", "favs", "ns/p")
    assert len(store.list_collection_items("ns", "favs")) == 1


def test_add_to_collection_missing_collection_raises(store: VersionStore, prompt) -> None:
    with pytest.raises(KeyError):
        store.add_to_collection("nobody", "nope", "ns/p")


def test_add_to_collection_missing_prompt_raises(store: VersionStore) -> None:
    store.create_collection("ns", "favs")
    with pytest.raises(KeyError):
        store.add_to_collection("ns", "favs", "nobody/ghost")


def test_remove_from_collection(store: VersionStore, prompt) -> None:
    store.create_collection("ns", "favs")
    store.add_to_collection("ns", "favs", "ns/p")
    assert store.remove_from_collection("ns", "favs", "ns/p") is True
    assert store.list_collection_items("ns", "favs") == []


def test_remove_from_collection_missing_collection_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.remove_from_collection("nobody", "nope", "ns/p")


def test_remove_from_collection_missing_prompt_returns_false(store: VersionStore) -> None:
    store.create_collection("ns", "favs")
    assert store.remove_from_collection("ns", "favs", "nobody/ghost") is False


def test_list_collection_items_missing_collection_raises(store: VersionStore) -> None:
    with pytest.raises(KeyError):
        store.list_collection_items("nobody", "nope")


def test_delete_collection_also_removes_items(store: VersionStore, prompt) -> None:
    store.create_collection("ns", "favs")
    store.add_to_collection("ns", "favs", "ns/p")
    store.delete_collection("ns", "favs")
    # recreate to verify items are gone
    store.create_collection("ns", "favs")
    assert store.list_collection_items("ns", "favs") == []
