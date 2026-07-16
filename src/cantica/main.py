"""
FastAPI application factory for the Cantica API server.

``create_app()`` assembles the full application:

- Mounts the v1 router under ``/v1`` (all prompt, version, tag, branch, fork,
  star, comment, collection, diff, render, resolve, hook, and auth endpoints).
- Mounts the MCP server under ``/mcp`` (HTTP/streamable-HTTP transport) so AI
  agents can discover and use prompts without the REST layer.
- Adds CORS middleware with open origins (``*``) suitable for local and
  community use; tighten in production via a proxy.
- Registers two meta endpoints:
    ``GET /health``                     — liveness probe returning ``{"status": "ok"}``
    ``GET /.well-known/cantica.json``   — service discovery document with API URL
                                          and webhook URL.
- Calls ``setup_logging()`` so structured log output is ready before the first
  request.

The module-level ``app`` singleton is what Uvicorn imports (``cantica.main:app``).
Use ``cantica serve`` (CLI) or point a WSGI runner directly at this object.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# Third party imports:
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports:
from cantica.api.v1.router import build_router
from cantica.api.v1.router import router as v1_router
from cantica.core.logger import setup_logging


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Run bootstrap tasks (user seeding, first-install key) then serve."""
    # Local imports:
    from cantica.api.deps import get_auth_config, get_store  # noqa: PLC0415
    from cantica.config import get_settings  # noqa: PLC0415
    from cantica.core.auth_provider import LocalAuthProvider  # noqa: PLC0415

    settings = get_settings()
    if settings.auth_enabled:
        await LocalAuthProvider(get_store(), get_auth_config()).bootstrap()
    yield


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application instance."""
    setup_logging()
    app = FastAPI(
        title="Cantica",
        description="A versioned, community-driven vault for AI prompts.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Local imports:
    from cantica.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if settings.security_shim:
        # Extraction roadmap Phase C: cantica-secure serves the security
        # surface; the in-repo security endpoints are omitted (code stays as
        # the flag-off path).
        # Local imports:
        from cantica.core.security_shim import build_security_shim  # noqa: PLC0415

        app.include_router(build_router(include_security=False), prefix="/v1")
        build_security_shim(settings).mount(app, prefix="/v1")
    else:
        app.include_router(v1_router, prefix="/v1")

    # Local imports:
    from cantica.mcp.server import mcp as _mcp  # noqa: PLC0415

    app.mount("/mcp", _mcp.http_app(path="/"))

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Return a simple liveness probe response."""
        return {"status": "ok"}

    @app.get("/.well-known/cantica.json", tags=["meta"])
    def discovery() -> dict[str, str]:
        """Return the well-known discovery document for Cantica API clients."""
        return {
            "version": "0.1",
            "api_url": "/v1",
            "webhooks_url": "/v1/hooks",
        }

    return app


app = create_app()
