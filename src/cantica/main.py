# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports:
from cantica.api.v1.router import router as v1_router
from cantica.core.logger import setup_logging


def create_app() -> FastAPI:
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
        return {"status": "ok"}

    @app.get("/.well-known/cantica.json", tags=["meta"])
    def discovery() -> dict[str, str]:
        return {
            "version": "0.1",
            "api_url": "/v1",
            "webhooks_url": "/v1/hooks",
        }

    return app


app = create_app()
