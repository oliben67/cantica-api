"""
MCP server for Cantica — exposes the prompt registry to AI agents.

Registers five tools and two resource templates on a ``FastMCP`` instance
(``mcp``).  The same instance is mounted at ``/mcp`` in the FastAPI app
(HTTP transport) and driven via stdio when ``cantica mcp`` is invoked.

Tools
-----
list_prompts     List prompts, optionally filtered by namespace, tag, or model.
search_prompts   Full-text search across prompt names, descriptions, and tags.
get_prompt       Retrieve a specific version's content and metadata.
render_prompt    Resolve a version and substitute ``{{variable}}`` placeholders.
commit_prompt    Write a new version (requires ``CANTICA_MCP_API_KEY`` when
                 ``CANTICA_AUTH_ENABLED=true``).

Resources
---------
``cantica://prompts/{namespace}/{name}``
    Latest content of a prompt (resolves the default-branch HEAD).
``cantica://prompts/{namespace}/{name}/versions/{ref}``
    Content at a specific ref (tag name, branch name, full SHA, or SHA prefix).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from typing import Any

# Third party imports:
from fastmcp import FastMCP

# Local imports:
from cantica.api.deps import get_store
from cantica.config import get_settings
from cantica.models import VariableSchema
from cantica.services.template_engine import TemplateEngine

mcp = FastMCP(
    "Cantica",
    instructions=(
        "Community-driven versioned prompt registry for AI agents. "
        "Use list_prompts or search_prompts to discover prompts, "
        "get_prompt to retrieve content, render_prompt to apply variables, "
        "and commit_prompt to publish new versions."
    ),
)

_engine = TemplateEngine()


@mcp.tool()
def list_prompts(
    namespace: str | None = None,
    tag: str | None = None,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """List prompts, optionally filtered by namespace, tag, or model hint."""
    store = get_store()
    prompts = store.list_prompts(namespace=namespace, tag=tag, model=model)
    return [
        {
            "slug": p.slug,
            "description": p.description,
            "tags": p.tags,
            "model_hints": p.model_hints,
            "visibility": p.visibility,
        }
        for p in prompts
    ]


@mcp.tool()
def search_prompts(q: str, namespace: str | None = None) -> list[dict[str, Any]]:
    """Full-text search across prompt names, descriptions, and tags."""
    store = get_store()
    prompts = store.search_prompts(q, namespace=namespace)
    return [{"slug": p.slug, "description": p.description, "tags": p.tags} for p in prompts]


@mcp.tool()
def get_prompt(namespace: str, name: str, ref: str = "latest") -> dict[str, Any]:
    """Retrieve a prompt version's content and metadata.

    ref: branch, tag, full SHA, or SHA prefix. Defaults to "latest".
    """
    store = get_store()
    try:
        version = store.resolve(namespace, name, ref)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    return {
        "slug": f"{namespace}/{name}",
        "sha": version.sha,
        "content": version.content,
        "message": version.message,
        "author": version.author,
        "variables": [v.model_dump() for v in version.variables],
        "created_at": version.created_at.isoformat(),
        "description": prompt.description if prompt else "",
    }


@mcp.tool()
def render_prompt(
    namespace: str,
    name: str,
    variables: dict[str, str] | None = None,
    ref: str = "latest",
) -> dict[str, Any]:
    """Render a prompt by substituting {{variable}} placeholders.

    Schema-declared defaults are applied first; `variables` overrides them.
    """
    store = get_store()
    try:
        version = store.resolve(namespace, name, ref)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    content = _engine.render_with_defaults(version.content, version.variables, variables or {})
    return {"content": content, "slug": f"{namespace}/{name}", "sha": version.sha, "ref": ref}


@mcp.tool()
def commit_prompt(
    namespace: str,
    name: str,
    content: str,
    message: str,
    branch: str = "main",
    variables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Commit a new version. Creates the prompt and namespace if they do not exist.

    When auth is enabled, CANTICA_MCP_API_KEY must be set to a valid active API key.
    """
    store = get_store()
    settings = get_settings()

    author = "mcp"
    if settings.auth_enabled:
        if not settings.mcp_api_key:
            raise ValueError("CANTICA_MCP_API_KEY must be configured when auth is enabled")
        # Local imports:
        from cantica.core.security import hash_api_key  # noqa: PLC0415

        meta = store.verify_api_key(hash_api_key(settings.mcp_api_key))
        if not meta:
            raise ValueError("CANTICA_MCP_API_KEY is not a valid active API key")
        author = meta["name"]

    prompt = store.get_prompt(namespace, name)
    if prompt is None:
        prompt = store.create_prompt(namespace, name)

    var_schemas = [VariableSchema(**v) for v in (variables or [])]
    version = store.commit(prompt.id, content, message, author, branch, var_schemas)
    return {"sha": version.sha, "slug": f"{namespace}/{name}", "branch": branch}


@mcp.resource("cantica://prompts/{namespace}/{name}")
def prompt_latest_resource(namespace: str, name: str) -> str:
    """Latest content of a prompt."""
    store = get_store()
    try:
        version = store.resolve(namespace, name, "latest")
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    return version.content


@mcp.resource("cantica://prompts/{namespace}/{name}/versions/{ref}")
def prompt_ref_resource(namespace: str, name: str, ref: str) -> str:
    """Content of a prompt at a specific ref (tag, branch, or SHA prefix)."""
    store = get_store()
    try:
        version = store.resolve(namespace, name, ref)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    return version.content
