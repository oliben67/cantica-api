# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Third party imports:
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Local imports:
from cantica.config import Settings
from cantica.shim import CanticaShim, TokenInfo, TokenResult


@pytest.fixture
def shim(tmp_path: Path) -> CanticaShim:
    s = CanticaShim(vault_path=tmp_path)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_init_with_vault_path(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path)
    assert shim.store is not None
    shim.close()


def test_init_with_settings(tmp_path: Path) -> None:
    shim = CanticaShim(settings=Settings(vault_path=tmp_path))
    assert shim.store is not None
    shim.close()


def test_init_with_database_url(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path, database_url=f"sqlite:///{tmp_path}/custom.db")
    shim.close()


# ---------------------------------------------------------------------------
# namespaces
# ---------------------------------------------------------------------------


async def test_namespaces_create_and_get(shim: CanticaShim) -> None:
    ns = await shim.namespaces.create("acme", "ACME corp")
    assert ns.name == "acme"
    assert await shim.namespaces.get("acme") is not None
    assert await shim.namespaces.get("missing") is None


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


async def test_prompts_create_get_list_delete(shim: CanticaShim) -> None:
    p = await shim.prompts.create("acme", "welcome", "A welcome prompt")
    assert p.namespace == "acme"
    assert await shim.prompts.get("acme", "welcome") is not None
    assert await shim.prompts.get("acme", "missing") is None
    assert any(r.name == "welcome" for r in await shim.prompts.list())
    assert len(await shim.prompts.list(namespace="acme")) == 1
    await shim.prompts.delete("acme", "welcome")
    assert await shim.prompts.get("acme", "welcome") is None


async def test_prompts_search(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "greeting", "A greeting prompt", tags=["hello"])
    assert any(r.name == "greeting" for r in await shim.prompts.search("greeting"))
    assert len(await shim.prompts.list(tag="hello")) == 1


async def test_prompts_list_filters(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "gpt-prompt", model_hints=["gpt-4"])
    assert len(await shim.prompts.list(model="gpt-4")) == 1
    assert len(await shim.prompts.list(visibility="public")) == 1


async def test_prompts_create_with_visibility_str(shim: CanticaShim) -> None:
    p = await shim.prompts.create("acme", "private-prompt", visibility="private")
    assert p.visibility.value == "private"


async def test_prompts_delete_missing_raises(shim: CanticaShim) -> None:
    with pytest.raises(KeyError):
        await shim.prompts.delete("missing", "prompt")


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------


async def test_versions_commit_and_log(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hello world", "Initial", "alice")
    assert v.content == "Hello world"
    log = await shim.versions.log("acme", "hello")
    assert len(log) == 1
    assert log[0].sha == v.sha


async def test_versions_get(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    assert await shim.versions.get(v.sha) is not None
    assert await shim.versions.get("0" * 64) is None


async def test_versions_resolve(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hello", "msg", "alice")
    v = await shim.versions.resolve("acme", "hello", "latest")
    assert v.content == "Hello"


async def test_versions_has_version(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    assert await shim.versions.has_version(v.sha)
    assert not await shim.versions.has_version("0" * 64)


async def test_versions_import_version(shim: CanticaShim) -> None:
    # Standard library imports:
    import hashlib

    await shim.prompts.create("acme", "hello")
    content = "Imported content"
    author = "bob"
    message = "Import"
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    content_sha = hashlib.sha256(content.encode()).hexdigest()
    commit_data = f"commit\n{content_sha}\n\n{author}\n{message}\n{created_at.isoformat()}"
    sha = hashlib.sha256(commit_data.encode()).hexdigest()

    imported = await shim.versions.import_version(
        "acme",
        "hello",
        sha=sha,
        content=content,
        message=message,
        author=author,
        branch="main",
        parent_sha=None,
        created_at=created_at,
    )
    assert imported.content == content


async def test_versions_render(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "templ")
    await shim.versions.commit("acme", "templ", "Hello {{name}}!", "Initial", "alice")
    assert (
        await shim.versions.render("acme", "templ", variables={"name": "world"}) == "Hello world!"
    )


async def test_versions_commit_missing_prompt_raises(shim: CanticaShim) -> None:
    with pytest.raises(KeyError):
        await shim.versions.commit("missing", "prompt", "content", "msg", "alice")


# ---------------------------------------------------------------------------
# branches
# ---------------------------------------------------------------------------


async def test_branches_create_get_list(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    b = await shim.branches.create("acme", "hello", "feature", v.sha)
    assert b.name == "feature"
    assert await shim.branches.get("acme", "hello", "feature") is not None
    names = [br.name for br in await shim.branches.list("acme", "hello")]
    assert "main" in names and "feature" in names


async def test_branches_merge_and_rollback(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v1 = await shim.versions.commit("acme", "hello", "v1", "First", "alice")
    await shim.branches.create("acme", "hello", "dev", v1.sha)
    await shim.versions.commit("acme", "hello", "v2", "Second", "alice", branch="dev")
    merged = await shim.branches.merge("acme", "hello", "dev", "main")
    assert merged.content == "v2"
    rolled = await shim.branches.rollback("acme", "hello", v1.sha)
    assert rolled.content == "v1"


async def test_branches_missing_prompt_raises(shim: CanticaShim) -> None:
    with pytest.raises(KeyError):
        await shim.branches.list("missing", "prompt")


async def test_branches_get_missing(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    assert await shim.branches.get("acme", "hello", "nonexistent") is None


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------


async def test_tags_create_get_list(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    t = await shim.tags.create("acme", "hello", "v1.0", v.sha)
    assert t.name == "v1.0"
    assert await shim.tags.get("acme", "hello", "v1.0") is not None
    assert await shim.tags.get("acme", "hello", "missing") is None
    assert any(tag.name == "v1.0" for tag in await shim.tags.list("acme", "hello"))


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


async def test_diff_compute(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v1 = await shim.versions.commit("acme", "hello", "Hello world", "First", "alice")
    v2 = await shim.versions.commit("acme", "hello", "Hello universe", "Second", "alice")
    diff = await shim.diff.compute(v1.sha, v2.sha)
    assert "world" in diff or "universe" in diff


# ---------------------------------------------------------------------------
# forks
# ---------------------------------------------------------------------------


async def test_forks_create_and_list(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hi", "First", "alice")
    fork = await shim.forks.create("acme", "hello", "acme", "hello-fork")
    assert fork.fork_slug == "acme/hello-fork"
    forks = await shim.forks.list("acme", "hello")
    assert len(forks) == 1


# ---------------------------------------------------------------------------
# stars
# ---------------------------------------------------------------------------


async def test_stars_star_unstar_list(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    star = await shim.stars.star("acme", "hello", "bob")
    assert star is not None
    assert len(await shim.stars.list("acme", "hello")) == 1
    assert await shim.stars.unstar("acme", "hello", "bob") is True
    assert len(await shim.stars.list("acme", "hello")) == 0


# ---------------------------------------------------------------------------
# comments
# ---------------------------------------------------------------------------


async def test_comments_add_list_delete(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    c = await shim.comments.add("acme", "hello", "Nice prompt!", "bob")
    assert c.body == "Nice prompt!"
    assert len(await shim.comments.list("acme", "hello")) == 1
    assert await shim.comments.delete(c.id) is True
    assert len(await shim.comments.list("acme", "hello")) == 0


async def test_comments_with_version_sha(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "First", "alice")
    c = await shim.comments.add("acme", "hello", "On version", "bob", version_sha=v.sha)
    by_version = await shim.comments.list("acme", "hello", version_sha=v.sha)
    assert len(by_version) == 1
    assert by_version[0].id == c.id


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------


async def test_collections_full_lifecycle(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hi", "First", "alice")
    col = await shim.collections.create("acme", "my-col", "A collection")
    assert col.name == "my-col"
    assert await shim.collections.get("acme", "my-col") is not None
    assert await shim.collections.get("acme", "missing") is None
    assert any(c.name == "my-col" for c in await shim.collections.list())
    assert len(await shim.collections.list(namespace="acme")) == 1
    await shim.collections.add_item("acme", "my-col", "acme/hello")
    items = await shim.collections.list_items("acme", "my-col")
    assert any(i.name == "hello" for i in items)
    assert await shim.collections.remove_item("acme", "my-col", "acme/hello") is True
    assert await shim.collections.delete("acme", "my-col") is True
    assert await shim.collections.get("acme", "my-col") is None


# ---------------------------------------------------------------------------
# webhooks
# ---------------------------------------------------------------------------


async def test_webhooks_create_list_delete(shim: CanticaShim) -> None:
    wh = await shim.webhooks.create(
        "https://example.com/hook", "secret", events=["version.created"]
    )
    assert wh.url == "https://example.com/hook"
    assert len(await shim.webhooks.list()) == 1
    assert await shim.webhooks.delete(wh.id) is True
    assert len(await shim.webhooks.list()) == 0


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


async def test_auth_create_list_revoke(shim: CanticaShim) -> None:
    result = await shim.auth.create_token("my-token")
    assert isinstance(result, TokenResult)
    assert result.name == "my-token"
    assert len(result.key) > 10
    tokens = await shim.auth.list_tokens()
    assert len(tokens) == 1
    assert isinstance(tokens[0], TokenInfo)
    assert await shim.auth.revoke_token(result.id) is True
    assert len(await shim.auth.list_tokens()) == 0


# ---------------------------------------------------------------------------
# mount / FastAPI integration
# ---------------------------------------------------------------------------


def test_mount_registers_routes(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path)
    app = FastAPI()
    shim.mount(app, prefix="/api/v1")
    with TestClient(app) as client:
        assert client.get("/api/v1/prompts").status_code == 200
    shim.close()


def test_mount_uses_shims_store(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path)
    shim.store.create_prompt("acme", "hello")
    app = FastAPI()
    shim.mount(app, prefix="/api/v1")
    with TestClient(app) as client:
        resp = client.get("/api/v1/prompts/acme/hello")
        assert resp.status_code == 200
        assert resp.json()["name"] == "hello"
    shim.close()


# ---------------------------------------------------------------------------
# lifespan
# ---------------------------------------------------------------------------


async def test_lifespan_closes_store(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path)
    async with shim.lifespan():
        pass


def test_wrap_lifespan_no_existing(tmp_path: Path) -> None:
    shim = CanticaShim(vault_path=tmp_path)
    app = FastAPI(lifespan=shim.wrap_lifespan())
    shim.mount(app, prefix="/api/v1")
    with TestClient(app) as client:
        assert client.get("/api/v1/prompts").status_code == 200


def test_wrap_lifespan_with_existing(tmp_path: Path) -> None:
    sentinel: list[str] = []

    @asynccontextmanager
    async def existing_lifespan(app: FastAPI):  # type: ignore[override]
        sentinel.append("started")
        yield
        sentinel.append("stopped")

    shim = CanticaShim(vault_path=tmp_path)
    app = FastAPI(lifespan=shim.wrap_lifespan(existing_lifespan))
    shim.mount(app, prefix="/api/v1")
    with TestClient(app):
        pass

    assert sentinel == ["started", "stopped"]


# ---------------------------------------------------------------------------
# export.to_json
# ---------------------------------------------------------------------------


async def test_export_to_json_empty(shim: CanticaShim) -> None:
    lines = [line async for line in shim.export.to_json()]
    assert lines == []


async def test_export_to_json_full(shim: CanticaShim) -> None:
    await shim.namespaces.create("acme", "ACME corp")
    await shim.prompts.create("acme", "hello", "A greeting")
    v = await shim.versions.commit("acme", "hello", "Hello world", "Initial", "alice")
    await shim.tags.create("acme", "hello", "v1.0", v.sha)

    lines = [line async for line in shim.export.to_json()]
    records = [json.loads(line) for line in lines]

    types = [r["type"] for r in records]
    assert "namespace" in types
    assert "prompt" in types
    assert "version" in types
    assert "tag" in types
    assert "checkpoint" in types

    ns_rec = next(r for r in records if r["type"] == "namespace")
    assert ns_rec["name"] == "acme"

    p_rec = next(r for r in records if r["type"] == "prompt")
    assert p_rec["name"] == "hello"
    assert p_rec["namespace"] == "acme"

    v_rec = next(r for r in records if r["type"] == "version")
    assert v_rec["sha"] == v.sha
    assert v_rec["content"] == "Hello world"

    tag_rec = next(r for r in records if r["type"] == "tag")
    assert tag_rec["tag_name"] == "v1.0"

    cp_rec = next(r for r in records if r["type"] == "checkpoint")
    assert "created_at" in cp_rec


async def test_export_to_json_since_filter(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v1 = await shim.versions.commit("acme", "hello", "First", "msg", "alice")
    v2 = await shim.versions.commit("acme", "hello", "Second", "msg", "alice")

    all_lines = [line async for line in shim.export.to_json()]
    since_v1 = [line async for line in shim.export.to_json(since=v1.created_at)]

    all_versions = [json.loads(ln) for ln in all_lines if json.loads(ln)["type"] == "version"]
    since_versions = [json.loads(ln) for ln in since_v1 if json.loads(ln)["type"] == "version"]

    assert len(all_versions) == 2
    assert len(since_versions) == 1
    assert since_versions[0]["sha"] == v2.sha


async def test_export_to_json_namespace_filter(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.prompts.create("other", "world")
    await shim.versions.commit("acme", "hello", "A", "msg", "alice")
    await shim.versions.commit("other", "world", "B", "msg", "bob")

    lines = [line async for line in shim.export.to_json(namespace="acme")]
    records = [json.loads(line) for line in lines]

    ns_names = [r["name"] for r in records if r["type"] == "namespace"]
    assert ns_names == ["acme"]

    v_names = [r["namespace"] for r in records if r["type"] == "version"]
    assert all(n == "acme" for n in v_names)


# ---------------------------------------------------------------------------
# export.ingest
# ---------------------------------------------------------------------------


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def test_export_ingest_roundtrip(shim: CanticaShim, tmp_path: Path) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hello world", "Initial", "alice")
    await shim.tags.create("acme", "hello", "v1.0", v.sha)

    export_data = b"".join([line async for line in shim.export.to_json()])

    target = CanticaShim(vault_path=tmp_path / "target")
    try:
        result = await target.export.ingest(_stream(export_data))
        assert result["errors"] == []
        assert result["imported"] > 0
        assert await target.prompts.get("acme", "hello") is not None
        assert await target.versions.get(v.sha) is not None
        assert await target.tags.get("acme", "hello", "v1.0") is not None
    finally:
        target.close()


async def test_export_ingest_idempotent(shim: CanticaShim, tmp_path: Path) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hello", "msg", "alice")

    export_data = b"".join([line async for line in shim.export.to_json()])

    target = CanticaShim(vault_path=tmp_path / "target")
    try:
        first = await target.export.ingest(_stream(export_data))
        second = await target.export.ingest(_stream(export_data))
        assert first["errors"] == []
        assert second["errors"] == []
        assert second["imported"] == 0
        assert second["skipped"] > 0
    finally:
        target.close()


async def test_export_ingest_invalid_json(shim: CanticaShim) -> None:
    async def _bad_stream() -> AsyncIterator[bytes]:
        yield b"not json\n"
        yield b'{"type": "checkpoint", "created_at": "2024-01-01T00:00:00"}\n'

    result = await shim.export.ingest(_bad_stream())
    assert len(result["errors"]) == 1
    assert "invalid JSON" in result["errors"][0]


async def test_export_ingest_version_missing_prompt(shim: CanticaShim) -> None:
    # Standard library imports:
    import hashlib

    content = "Hi"
    author = "alice"
    message = "msg"
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    commit_data = f"commit\n{content_sha}\n\n{author}\n{message}\n{created_at.isoformat()}"
    sha = hashlib.sha256(commit_data.encode()).hexdigest()

    rec = json.dumps(
        {
            "type": "version",
            "namespace": "missing",
            "name": "prompt",
            "sha": sha,
            "content": content,
            "message": message,
            "author": author,
            "branch": "main",
            "parent_sha": None,
            "created_at": created_at.isoformat(),
            "variables": [],
        }
    )

    async def _stream_rec() -> AsyncIterator[bytes]:
        yield (rec + "\n").encode()

    result = await shim.export.ingest(_stream_rec())
    assert len(result["errors"]) == 1


async def test_export_ingest_unknown_type(shim: CanticaShim) -> None:
    rec = json.dumps({"type": "unknown_record"})

    async def _s() -> AsyncIterator[bytes]:
        yield (rec + "\n").encode()

    result = await shim.export.ingest(_s())
    assert result["imported"] == 0
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# export.push (HTTP endpoint)
# ---------------------------------------------------------------------------


def test_push_endpoint_via_http(tmp_path: Path) -> None:
    source = CanticaShim(vault_path=tmp_path / "source")
    target = CanticaShim(vault_path=tmp_path / "target")
    try:
        source.store.create_namespace("acme")
        source.store.create_prompt("acme", "hello")
        source.store.commit(source.store.get_prompt("acme", "hello").id, "Hi", "Initial", "alice")

        app = FastAPI()
        target.mount(app, prefix="/api/v1")

        export_data = b""
        # Standard library imports:
        import asyncio

        async def _collect() -> bytes:
            chunks = []
            async for chunk in source.export.to_json():
                chunks.append(chunk)
            return b"".join(chunks)

        export_data = asyncio.run(_collect())

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/push",
                content=export_data,
                headers={"Content-Type": "application/x-ndjson"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["imported"] > 0

        assert target.store.get_prompt("acme", "hello") is not None
    finally:
        source.close()
        target.close()


# ---------------------------------------------------------------------------
# export.push (mock httpx for unit coverage)
# ---------------------------------------------------------------------------


async def test_export_push_calls_httpx(shim: CanticaShim) -> None:
    # Standard library imports:
    from unittest.mock import AsyncMock, MagicMock, patch

    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"imported": 1, "skipped": 0})

    posted_content: list[bytes] = []

    async def _fake_post(url: str, *, content: Any, headers: Any, timeout: Any) -> MagicMock:
        async for chunk in content:
            posted_content.append(chunk)
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = _fake_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await shim.export.push("http://remote/api/v1", "my-key")

    assert result["imported"] == 1
    assert any(b"hello" in chunk for chunk in posted_content)


# ---------------------------------------------------------------------------
# Additional coverage for uncovered branches
# ---------------------------------------------------------------------------


async def test_prompts_create_with_visibility_enum(shim: CanticaShim) -> None:
    # Local imports:
    from cantica.models import Visibility

    p = await shim.prompts.create("acme", "enum-vis", visibility=Visibility.private)
    assert p.visibility == Visibility.private


async def test_versions_resolve_uri(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    v = await shim.versions.resolve_uri("cantica://acme/hello")
    assert v.content == "Hi"


async def test_webhooks_fire(shim: CanticaShim) -> None:
    await shim.webhooks.create("https://example.com/hook", "secret", events=["version.created"])
    await shim.webhooks.fire("version.created", {"sha": "abc"})


async def test_export_ingest_empty_lines(shim: CanticaShim) -> None:
    async def _stream_with_empty() -> AsyncIterator[bytes]:
        yield b"\n\n"
        yield b'{"type": "namespace", "name": "acme", "description": ""}\n'

    result = await shim.export.ingest(_stream_with_empty())
    assert result["errors"] == []


async def test_export_ingest_tag_missing_prompt(shim: CanticaShim) -> None:
    rec = json.dumps(
        {
            "type": "tag",
            "namespace": "missing",
            "name": "prompt",
            "tag_name": "v1.0",
            "sha": "abc",
        }
    )

    async def _s() -> AsyncIterator[bytes]:
        yield (rec + "\n").encode()

    result = await shim.export.ingest(_s())
    assert result["errors"] == []
    assert result["imported"] == 0


async def test_export_ingest_tag_already_exists(shim: CanticaShim) -> None:
    await shim.prompts.create("acme", "hello")
    v = await shim.versions.commit("acme", "hello", "Hi", "msg", "alice")
    await shim.tags.create("acme", "hello", "v1.0", v.sha)

    rec = json.dumps(
        {
            "type": "tag",
            "namespace": "acme",
            "name": "hello",
            "tag_name": "v1.0",
            "sha": v.sha,
        }
    )

    async def _s() -> AsyncIterator[bytes]:
        yield (rec + "\n").encode()

    result = await shim.export.ingest(_s())
    assert result["errors"] == []
    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# namespace access control — shim
# ---------------------------------------------------------------------------


async def test_namespaces_list_and_update(shim: CanticaShim) -> None:
    await shim.namespaces.create("ns1")
    await shim.namespaces.create("ns2")
    names = {ns.name for ns in await shim.namespaces.list()}
    assert {"ns1", "ns2"}.issubset(names)

    updated = await shim.namespaces.update("ns1", description="updated")
    assert updated.description == "updated"


async def test_namespaces_create_proprietary_and_encoded(shim: CanticaShim) -> None:
    ns = await shim.namespaces.create("prop", is_proprietary=True, encoded=True)
    assert ns.is_proprietary is True
    assert ns.encoded is True


async def test_certificates_issue_list_revoke(shim: CanticaShim) -> None:
    await shim.namespaces.create("prop", is_proprietary=True)
    cert = await shim.certificates.issue("prop", "alice")
    assert cert.token is not None
    assert cert.namespace == "prop"

    certs = await shim.certificates.list("prop")
    assert len(certs) == 1
    assert certs[0].token is None  # not returned in list

    ok = await shim.certificates.revoke(cert.id)
    assert ok is True

    not_found = await shim.certificates.revoke("nonexistent-id")
    assert not_found is False


async def test_export_push_with_cert_token(shim: CanticaShim) -> None:
    """push() must include X-Cantica-Certificate header when cert_token is provided."""
    # Standard library imports:
    from unittest.mock import AsyncMock, MagicMock, patch

    await shim.prompts.create("acme", "hello")
    await shim.versions.commit("acme", "hello", "Hi", "init", "alice")

    captured_headers: dict[str, str] = {}
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"imported": 1, "skipped": 0})

    async def _fake_post(
        url: str, *, content: object, headers: object, timeout: object
    ) -> MagicMock:
        captured_headers.update(headers)  # type: ignore[arg-type]
        async for _ in content:
            pass
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = _fake_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        await shim.export.push("http://remote/api/v1", "mykey", cert_token="mytoken")

    assert captured_headers.get("X-Cantica-Certificate") == "mytoken"
