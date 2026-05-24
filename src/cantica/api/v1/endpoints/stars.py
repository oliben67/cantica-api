"""
FastAPI endpoints for prompt starring.

Router prefix: ``/v1/prompts``   Tag: ``stars``

Stars are a simple appreciation mechanism: a namespace (user) can star a
prompt at most once.  The ``star_count`` on ``PromptOrm`` is updated
atomically alongside the ``stars`` table row.

The actor namespace is taken from the authenticated user's ``id`` field, so
no body is required for star/unstar operations.

Endpoints
---------
``POST   /v1/prompts/{namespace}/{name}/star``
    Star a prompt.  Idempotent — returns the existing star record if the user
    has already starred it.  Returns HTTP 404 if the prompt does not exist.

``DELETE /v1/prompts/{namespace}/{name}/star``
    Remove the authenticated user's star from a prompt.  Returns HTTP 404 if
    the prompt does not exist.  No-op (HTTP 204) if the user had not starred it.

``GET    /v1/prompts/{namespace}/{name}/stargazers``
    List all namespaces that have starred the prompt.  Returns HTTP 404 if the
    prompt does not exist.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.stars import StarResponse

router = APIRouter(prefix="/prompts", tags=["stars"])


def _to_response(star) -> StarResponse:
    """Convert a ``Star`` domain object to its API response schema."""
    return StarResponse(**star.model_dump())


@router.post("/{namespace}/{name}/star", response_model=StarResponse, status_code=201)
def star_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    user: UserDep,
    cert_token: CertTokenDep = None,
) -> StarResponse:
    """Star a prompt on behalf of the authenticated namespace."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        star = store.star_prompt(namespace, name, user["id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(star)


@router.delete("/{namespace}/{name}/star", status_code=204)
def unstar_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Remove a star from a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        store.unstar_prompt(namespace, name, user["id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{namespace}/{name}/stargazers", response_model=list[StarResponse])
def list_stargazers(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> list[StarResponse]:
    """List all namespaces that have starred a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        stars = store.list_stargazers(namespace, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_to_response(s) for s in stars]
