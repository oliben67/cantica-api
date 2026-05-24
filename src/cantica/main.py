"""
FastAPI application factory for the Cantica API server.

``create_app()`` assembles the full application:

- Mounts the v1 router under ``/v1`` (all prompt, version, tag, branch, fork,
  star, comment, collection, diff, render, resolve, hook, and auth endpoints).
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

# Third party imports:
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports:
from cantica.api.v1.router import router as v1_router
from cantica.core.logger import setup_logging


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application instance."""
    setup_logging()
    app = FastAPI(
        title="Cantica",
        description="A versioned, community-driven vault for AI prompts.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(v1_router, prefix="/v1")

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
