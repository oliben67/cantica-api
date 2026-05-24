"""
FastAPI endpoint for resolving a ``cantica://`` URI to a concrete version.

Tag: ``resolve``

Endpoint
--------
``POST /v1/resolve``
    Resolve a ``cantica://`` URI and return the full ``VersionResponse``.
    Body: ``ResolveRequest`` (``uri``, optional ``remote_url``).

    URI forms accepted (via ``parse_address``):
    - ``cantica://namespace/name``          → local vault, latest
    - ``cantica://namespace/name@ref``      → local vault at ref
    - ``cantica://host/namespace/name@ref`` → fetch from remote host (HTTP GET)

    When the URI includes a host component, the ``remote_url`` field can
    override the derived host URL (useful behind proxies).

    Error mapping:
    - HTTP 422 — malformed URI (``ValueError``)
    - HTTP 404 — prompt or ref not found (``KeyError``)
    - HTTP 502 — upstream remote unreachable (``ConnectionError``)
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.resolve import ResolveRequest
from cantica.schemas.versions import VersionResponse

router = APIRouter(tags=["resolve"])


@router.post("/resolve", response_model=VersionResponse)
def resolve_uri(
    body: ResolveRequest,
    store: StoreDep,
    _user: UserDep,
) -> VersionResponse:
    """Resolve a cantica:// URI and return the matching version."""
    try:
        version = store.resolve_uri(body.uri, body.remote_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VersionResponse(**version.model_dump())
