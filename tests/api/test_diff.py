# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi.testclient import TestClient


def test_diff_two_versions(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/diff",
        json={"ref1": "v1.0", "ref2": "latest"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "-You are an architect." in data["diff"]
    assert "+You are a senior architect." in data["diff"]
    assert data["ref1"] == "v1.0"
    assert data["ref2"] == "latest"


def test_diff_identical_versions(client: TestClient, seeded: dict) -> None:
    sha = seeded["v1"].sha
    r = client.post(
        "/v1/prompts/osteck/architect/diff",
        json={"ref1": sha[:7], "ref2": sha[:7]},
    )
    assert r.status_code == 200
    assert r.json()["diff"] == ""


def test_diff_bad_ref(client: TestClient, seeded: dict) -> None:
    r = client.post(
        "/v1/prompts/osteck/architect/diff",
        json={"ref1": "v1.0", "ref2": "nonexistent"},
    )
    assert r.status_code == 404


def test_diff_prompt_not_found(client: TestClient) -> None:
    r = client.post(
        "/v1/prompts/nobody/nothing/diff",
        json={"ref1": "a", "ref2": "b"},
    )
    assert r.status_code == 404
