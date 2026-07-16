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
- ``federation``  — federation peer management and cross-instance fan-out (``/v1/federation``)
- ``federate``    — federation membership protocol (``/v1/federate``, ``/v1/federations``)
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter

# Local imports:
from cantica.api.v1.endpoints import (
    admin,
    auth,
    branches,
    collections,
    comments,
    diff,
    federate,
    federation,
    forks,
    hooks,
    invites,
    keyauth,
    namespaces,
    prompts,
    push,
    render,
    resolve,
    sessions,
    stars,
    tags,
    upload,
    versions,
)


def build_router(*, include_security: bool = True) -> APIRouter:
    """Assemble the v1 router.

    With ``include_security=False`` the in-repo security endpoints (token
    management, keyauth, sessions, invites, admin user management) are omitted;
    the mounted cantica-secure shim serves those paths instead (extraction
    roadmap Phase C). Domain routers are always included and continue to
    authorize through ``get_current_user``, which delegates to the shim when
    the flag is on.
    """
    r = APIRouter()
    r.include_router(prompts.router)
    r.include_router(versions.router)
    r.include_router(tags.router)
    r.include_router(branches.router)
    r.include_router(forks.router)
    r.include_router(stars.router)
    r.include_router(comments.router)
    r.include_router(collections.router)
    r.include_router(diff.router)
    r.include_router(render.router)
    r.include_router(resolve.router)
    r.include_router(hooks.router)
    r.include_router(push.router)
    r.include_router(namespaces.router)
    r.include_router(federation.router)
    r.include_router(federate.router)
    r.include_router(upload.router)
    if include_security:
        r.include_router(auth.router)
        r.include_router(keyauth.router)
        r.include_router(sessions.router)
        r.include_router(admin.router)
        r.include_router(invites.router)
    return r


# Flag-off path (unchanged surface), included by main.py at /v1
router = build_router()
