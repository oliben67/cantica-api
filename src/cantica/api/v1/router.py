"""
Top-level v1 API router: aggregates all endpoint sub-routers.

``router`` is a plain ``APIRouter`` that collects every feature router defined
under ``api/v1/endpoints/``.  It is mounted at ``/v1`` by the application
factory in ``main.py``.

Included routers (in registration order):
- ``prompts``     — prompt CRUD (``/v1/prompts``)
- ``versions``    — commit and retrieve versions (``/v1/prompts/{ns}/{name}/versions``)
- ``tags``        — tag management (``/v1/prompts/{ns}/{name}/tags``)
- ``branches``    — branch create / list / rollback / merge
- ``forks``       — fork and list forks
- ``stars``       — star / unstar / list stargazers
- ``comments``    — add / list / delete comments
- ``collections`` — collection CRUD + item management (``/v1/collections``)
- ``diff``        — unified diff between two refs
- ``render``      — render prompt with variable substitution (``/v1/render``)
- ``resolve``     — resolve a ``cantica://`` URI to a version (``/v1/resolve``)
- ``hooks``       — webhook CRUD (``/v1/hooks``)
- ``auth``        — API token management (``/v1/tokens``)
- ``push``        — NDJSON streaming push ingestion (``/v1/push``)
- ``namespaces``  — namespace CRUD + certificate management (``/v1/namespaces``)
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter

# Local imports:
from cantica.api.v1.endpoints import (
    auth,
    branches,
    collections,
    comments,
    diff,
    forks,
    hooks,
    namespaces,
    prompts,
    push,
    render,
    resolve,
    stars,
    tags,
    versions,
)

router = APIRouter()

router.include_router(prompts.router)
router.include_router(versions.router)
router.include_router(tags.router)
router.include_router(branches.router)
router.include_router(forks.router)
router.include_router(stars.router)
router.include_router(comments.router)
router.include_router(collections.router)
router.include_router(diff.router)
router.include_router(render.router)
router.include_router(resolve.router)
router.include_router(hooks.router)
router.include_router(auth.router)
router.include_router(push.router)
router.include_router(namespaces.router)
