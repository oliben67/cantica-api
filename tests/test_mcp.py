# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path
from unittest.mock import patch

# Third party imports:
import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.exceptions import ToolError
from typer.testing import CliRunner

# Local imports:
from cantica.cli import app
from cantica.config import Settings
from cantica.mcp import server as mcp_mod
from cantica.mcp.server import mcp
from cantica.models import VariableSchema
from cantica.services.version_store import VersionStore

runner = CliRunner()


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    s = VersionStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def mcp_env(store: VersionStore, monkeypatch: pytest.MonkeyPatch) -> VersionStore:
    """Wire the MCP server module to use the test store and auth-disabled settings."""
    settings = Settings(auth_enabled=False, mcp_api_key="")
    monkeypatch.setattr(mcp_mod, "get_store", lambda: store)
    monkeypatch.setattr(mcp_mod, "get_settings", lambda: settings)
    return store


@pytest.fixture
def seeded(mcp_env: VersionStore) -> dict:
    store = mcp_env
    prompt = store.create_prompt("acme", "chat-system", "A chat system prompt")
    v1 = store.commit(prompt.id, "You are a helpful assistant.", "Initial", "alice")
    v2 = store.commit(prompt.id, "You are a very helpful assistant.", "Friendlier", "alice")
    store.create_tag(prompt.id, "v1.0", v1.sha)
    return {"store": store, "prompt": prompt, "v1": v1, "v2": v2}


# --------------------------------------------------------------------------- #
# list_prompts                                                                 #
# --------------------------------------------------------------------------- #


async def test_list_prompts_empty(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("list_prompts", {})
    assert result.data == []


async def test_list_prompts_returns_all(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("list_prompts", {})
    assert len(result.data) == 1
    assert result.data[0]["slug"] == "acme/chat-system"
    assert result.data[0]["description"] == "A chat system prompt"


async def test_list_prompts_namespace_filter(seeded: dict) -> None:
    store: VersionStore = seeded["store"]
    store.create_prompt("other", "other-prompt")
    async with Client(mcp) as client:
        result = await client.call_tool("list_prompts", {"namespace": "acme"})
    assert len(result.data) == 1
    assert result.data[0]["slug"] == "acme/chat-system"


async def test_list_prompts_tag_filter(seeded: dict) -> None:
    store: VersionStore = seeded["store"]
    store.create_prompt("acme", "tagged", tags=["science"])
    async with Client(mcp) as client:
        result = await client.call_tool("list_prompts", {"tag": "science"})
    assert len(result.data) == 1
    assert result.data[0]["slug"] == "acme/tagged"


async def test_list_prompts_model_filter(seeded: dict) -> None:
    store: VersionStore = seeded["store"]
    store.create_prompt("acme", "gpt-prompt", model_hints=["gpt-4"])
    async with Client(mcp) as client:
        result = await client.call_tool("list_prompts", {"model": "gpt-4"})
    assert len(result.data) == 1
    assert result.data[0]["slug"] == "acme/gpt-prompt"


# --------------------------------------------------------------------------- #
# search_prompts                                                               #
# --------------------------------------------------------------------------- #


async def test_search_prompts_finds_match(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("search_prompts", {"q": "chat"})
    assert any(r["slug"] == "acme/chat-system" for r in result.data)


async def test_search_prompts_no_match(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("search_prompts", {"q": "zzznomatch"})
    assert result.data == []


async def test_search_prompts_namespace_scoped(seeded: dict) -> None:
    store: VersionStore = seeded["store"]
    store.create_prompt("other", "chat-other", "another chat prompt")
    async with Client(mcp) as client:
        result = await client.call_tool("search_prompts", {"q": "chat", "namespace": "acme"})
    assert all(r["slug"].startswith("acme/") for r in result.data)


# --------------------------------------------------------------------------- #
# get_prompt                                                                   #
# --------------------------------------------------------------------------- #


async def test_get_prompt_latest(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_prompt", {"namespace": "acme", "name": "chat-system"})
    assert result.data["slug"] == "acme/chat-system"
    assert result.data["content"] == "You are a very helpful assistant."
    assert result.data["sha"] == seeded["v2"].sha


async def test_get_prompt_by_tag(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt", {"namespace": "acme", "name": "chat-system", "ref": "v1.0"}
        )
    assert result.data["content"] == "You are a helpful assistant."
    assert result.data["sha"] == seeded["v1"].sha


async def test_get_prompt_not_found(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="not found"):
            await client.call_tool("get_prompt", {"namespace": "nobody", "name": "nothing"})


# --------------------------------------------------------------------------- #
# render_prompt                                                                #
# --------------------------------------------------------------------------- #


async def test_render_prompt_static(mcp_env: VersionStore) -> None:
    prompt = mcp_env.create_prompt("acme", "static")
    mcp_env.commit(prompt.id, "Hello world.", "Initial", "alice")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_prompt", {"namespace": "acme", "name": "static"}
        )
    assert result.data["content"] == "Hello world."


async def test_render_prompt_with_variables(mcp_env: VersionStore) -> None:
    prompt = mcp_env.create_prompt("acme", "greeter")
    schema = [VariableSchema(name="name", type="string")]
    mcp_env.commit(prompt.id, "Hello {{name}}!", "Initial", "alice", variables=schema)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_prompt",
            {"namespace": "acme", "name": "greeter", "variables": {"name": "World"}},
        )
    assert result.data["content"] == "Hello World!"


async def test_render_prompt_uses_schema_defaults(mcp_env: VersionStore) -> None:
    prompt = mcp_env.create_prompt("acme", "defaulted")
    schema = [VariableSchema(name="lang", type="string", default="Python")]
    mcp_env.commit(prompt.id, "Speak {{lang}}.", "Initial", "alice", variables=schema)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_prompt", {"namespace": "acme", "name": "defaulted"}
        )
    assert result.data["content"] == "Speak Python."


async def test_render_prompt_not_found(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="not found"):
            await client.call_tool(
                "render_prompt", {"namespace": "nobody", "name": "nothing"}
            )


# --------------------------------------------------------------------------- #
# commit_prompt                                                                #
# --------------------------------------------------------------------------- #


async def test_commit_prompt_creates_new(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "commit_prompt",
            {
                "namespace": "acme",
                "name": "brand-new",
                "content": "New content.",
                "message": "Initial commit",
            },
        )
    assert result.data["slug"] == "acme/brand-new"
    assert result.data["branch"] == "main"
    assert len(result.data["sha"]) == 64
    assert mcp_env.get_prompt("acme", "brand-new") is not None


async def test_commit_prompt_appends_version(seeded: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "commit_prompt",
            {
                "namespace": "acme",
                "name": "chat-system",
                "content": "Updated content.",
                "message": "Update",
            },
        )
    store: VersionStore = seeded["store"]
    version = store.resolve("acme", "chat-system", "latest")
    assert version.content == "Updated content."
    assert version.sha == result.data["sha"]


async def test_commit_prompt_with_variables(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "commit_prompt",
            {
                "namespace": "acme",
                "name": "templated",
                "content": "Hello {{name}}.",
                "message": "Add template",
                "variables": [{"name": "name", "type": "string", "required": True}],
            },
        )
    assert result.data["slug"] == "acme/templated"
    version = mcp_env.resolve("acme", "templated", "latest")
    assert version.variables[0].name == "name"


async def test_commit_prompt_auth_disabled_no_key_needed(
    mcp_env: VersionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mcp_mod, "get_settings", lambda: Settings(auth_enabled=False, mcp_api_key="")
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "commit_prompt",
            {"namespace": "acme", "name": "x", "content": "c", "message": "m"},
        )
    assert result.data["sha"]


async def test_commit_prompt_auth_enabled_no_key_raises(
    mcp_env: VersionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mcp_mod, "get_settings", lambda: Settings(auth_enabled=True, mcp_api_key="")
    )
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="CANTICA_MCP_API_KEY"):
            await client.call_tool(
                "commit_prompt",
                {"namespace": "acme", "name": "x", "content": "c", "message": "m"},
            )


async def test_commit_prompt_auth_enabled_invalid_key_raises(
    mcp_env: VersionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mcp_mod,
        "get_settings",
        lambda: Settings(auth_enabled=True, mcp_api_key="bad-key"),
    )
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="not a valid"):
            await client.call_tool(
                "commit_prompt",
                {"namespace": "acme", "name": "x", "content": "c", "message": "m"},
            )


async def test_commit_prompt_auth_enabled_valid_key(
    mcp_env: VersionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Local imports:
    from cantica.core.security import hash_api_key

    raw_key = "my-secret-api-key"
    mcp_env.create_api_key("mcp-agent", hash_api_key(raw_key))
    monkeypatch.setattr(
        mcp_mod,
        "get_settings",
        lambda: Settings(auth_enabled=True, mcp_api_key=raw_key),
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "commit_prompt",
            {"namespace": "acme", "name": "authed", "content": "c", "message": "m"},
        )
    version = mcp_env.resolve("acme", "authed", "latest")
    assert version.author == "mcp-agent"
    assert result.data["sha"] == version.sha


# --------------------------------------------------------------------------- #
# Resources                                                                    #
# --------------------------------------------------------------------------- #


async def test_prompt_latest_resource(seeded: dict) -> None:
    async with Client(mcp) as client:
        contents = await client.read_resource("cantica://prompts/acme/chat-system")
    assert contents[0].text == "You are a very helpful assistant."


async def test_prompt_ref_resource_by_tag(seeded: dict) -> None:
    async with Client(mcp) as client:
        contents = await client.read_resource(
            "cantica://prompts/acme/chat-system/versions/v1.0"
        )
    assert contents[0].text == "You are a helpful assistant."


async def test_prompt_ref_resource_by_sha_prefix(seeded: dict) -> None:
    sha_prefix = seeded["v1"].sha[:8]
    async with Client(mcp) as client:
        contents = await client.read_resource(
            f"cantica://prompts/acme/chat-system/versions/{sha_prefix}"
        )
    assert contents[0].text == "You are a helpful assistant."


async def test_prompt_latest_resource_not_found(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.read_resource("cantica://prompts/nobody/nothing")


async def test_prompt_ref_resource_not_found(mcp_env: VersionStore) -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.read_resource("cantica://prompts/nobody/nothing/versions/v1")


# --------------------------------------------------------------------------- #
# CLI command                                                                  #
# --------------------------------------------------------------------------- #


def test_mcp_cli_invokes_stdio_run() -> None:
    with patch("cantica.mcp.server.mcp") as mock_mcp:
        result = runner.invoke(app, ["mcp"])
    assert result.exit_code == 0
    mock_mcp.run.assert_called_once_with("stdio")


# --------------------------------------------------------------------------- #
# HTTP mount                                                                   #
# --------------------------------------------------------------------------- #


def test_mcp_http_mount_reachable() -> None:
    """The /mcp path is mounted — POST doesn't 404."""
    # Local imports:
    from cantica.main import create_app

    fastapi_app = create_app()
    with TestClient(fastapi_app, raise_server_exceptions=False) as client:
        r = client.post("/mcp/", content=b"{}", headers={"content-type": "application/json"})
    assert r.status_code != 404
