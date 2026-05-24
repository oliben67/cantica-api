"""
FastAPI endpoints for tag management.

Router prefix: ``/v1/prompts``   Tag: ``tags``

Tags are named, mutable pointers to specific version SHAs (analogous to git
tags).  Creating a tag that already exists re-points it to the new SHA (upsert
semantics via ``store.create_tag``).

Endpoints
---------
``GET  /v1/prompts/{namespace}/{name}/tags``
    List all tags for a prompt, ordered by creation time (ascending).

``POST /v1/prompts/{namespace}/{name}/tags``
    Create or update a tag.  Body: ``TagCreate`` (``name``, ``sha``).
    Returns HTTP 404 if the prompt or SHA does not exist, HTTP 201 on success.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.tags import TagCreate, TagResponse

router = APIRouter(prefix="/prompts", tags=["tags"])


def _to_response(tag) -> TagResponse:
    """Convert a ``Tag`` domain object to its API response schema."""
    return TagResponse(**tag.model_dump())


@router.get("/{namespace}/{name}/tags", response_model=list[TagResponse])
def list_tags(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> list[TagResponse]:
    """List all tags for a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(t) for t in store.list_tags(prompt.id)]


@router.post("/{namespace}/{name}/tags", response_model=TagResponse, status_code=201)
def create_tag(
    namespace: str,
    name: str,
    body: TagCreate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> TagResponse:
    """Create a named tag pointing to a specific commit SHA."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if not store.get_version(body.sha):
        raise HTTPException(status_code=404, detail="SHA not found")
    tag = store.create_tag(prompt.id, body.name, body.sha)
    return _to_response(tag)
