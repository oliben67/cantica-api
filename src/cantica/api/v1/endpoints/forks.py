"""
FastAPI endpoints for forking prompts.

Router prefix: ``/v1/prompts``   Tag: ``forks``

Forking creates a full independent copy of a prompt (all versions, all tags)
under a new ``namespace/name`` slug.  The source prompt's ``fork_count``
counter is incremented and a ``ForkOrm`` lineage record is written so the
relationship is traceable.

Version SHAs are **not** preserved across forks — each version is re-committed
under the fork's own prompt ID, generating new SHAs that are unique to the
destination.

Endpoints
---------
``POST /v1/prompts/{namespace}/{name}/fork``
    Fork the prompt.  Body: ``ForkCreate`` (``dest_namespace``, ``dest_name``,
    optional ``branch`` defaulting to ``"main"``).
    Returns HTTP 404 if the source prompt does not exist.
    Returns HTTP 409 if the destination slug already exists.

``GET  /v1/prompts/{namespace}/{name}/forks``
    List all known forks of a prompt (lineage records only — not full prompt
    objects).  Returns HTTP 404 if the prompt does not exist.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.forks import ForkCreate, ForkResponse

router = APIRouter(prefix="/prompts", tags=["forks"])


def _to_response(fork) -> ForkResponse:
    """Convert a ``Fork`` domain object to its API response schema."""
    return ForkResponse(**fork.model_dump())


@router.post("/{namespace}/{name}/fork", response_model=ForkResponse, status_code=201)
def fork_prompt(
    namespace: str,
    name: str,
    body: ForkCreate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> ForkResponse:
    """Fork a prompt into a new namespace/name, copying its history."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        fork = store.fork(namespace, name, body.dest_namespace, body.dest_name, body.branch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(fork)


@router.get("/{namespace}/{name}/forks", response_model=list[ForkResponse])
def list_forks(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> list[ForkResponse]:
    """List all forks of a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not store.get_prompt(namespace, name):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(f) for f in store.list_forks(namespace, name)]
