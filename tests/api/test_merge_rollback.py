# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient

# ------------------------------------------------------------------ #
# rollback                                                             #
# ------------------------------------------------------------------ #


def test_rollback_to_ref(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.post(
        "/v1/prompts/osteck/architect/rollback",
        json={"ref": sha[:7], "branch": "main"},
    )
    assert r.status_code == 200
    assert r.json()["sha"] == sha


def test_rollback_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/rollback",
        json={"ref": "latest", "branch": "main"},
    )
    assert r.status_code == 404


def test_rollback_bad_ref(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/rollback",
        json={"ref": "nonexistent", "branch": "main"},
    )
    assert r.status_code == 404


# ------------------------------------------------------------------ #
# merge                                                                #
# ------------------------------------------------------------------ #


def test_merge_fast_forward(client: TestClient, seeded: dict, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    store = VersionStore(vault)
    prompt = store.get_prompt("osteck", "architect")
    # branch from main HEAD so fast-forward is possible
    store.create_branch(prompt.id, "feature", seeded["v2"].sha)
    store.commit(prompt.id, "Feature work", "Feature", "osteck", branch="feature")
    store.close()

    r = client.post(
        "/v1/prompts/osteck/architect/merge",
        json={"from_branch": "feature", "into_branch": "main"},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Feature"


def test_merge_already_up_to_date(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/merge",
        json={"from_branch": "main", "into_branch": "main"},
    )
    assert r.status_code == 200


def test_merge_source_not_found(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/merge",
        json={"from_branch": "nonexistent", "into_branch": "main"},
    )
    assert r.status_code == 404


def test_merge_diverged_returns_409(client: TestClient, seeded: dict, vault) -> None:
    # Local imports:
    from cantica.services.version_store import VersionStore

    store = VersionStore(vault)
    prompt = store.get_prompt("osteck", "architect")
    store.create_branch(prompt.id, "feature", seeded["v1"].sha)
    store.commit(prompt.id, "Feature", "Feature", "osteck", branch="feature")
    # advance main independently → diverged
    store.commit(prompt.id, "Main extra", "MainExtra", "osteck", branch="main")
    store.close()

    r = client.post(
        "/v1/prompts/osteck/architect/merge",
        json={"from_branch": "feature", "into_branch": "main"},
    )
    assert r.status_code == 409


def test_merge_prompt_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/merge",
        json={"from_branch": "feature", "into_branch": "main"},
    )
    assert r.status_code == 404
