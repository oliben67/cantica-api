"""
FastAPI endpoints for prompt CRUD operations.

Router prefix: ``/v1/prompts``   Tag: ``prompts``

Endpoints
---------
``GET    /v1/prompts``
    List all prompts.  Supports optional query filters: ``namespace``, ``tag``,
    ``model`` (model hint), and ``visibility``.  When the ``q`` parameter is
    provided, performs a full-text search via ``store.search_prompts()`` instead
    of a plain list.

``POST   /v1/prompts``
    Create a new prompt.  Body: ``PromptCreate``.  Returns HTTP 409 if the
    ``namespace/name`` slug already exists.

``GET    /v1/prompts/{namespace}/{name}``
    Retrieve a single prompt by its slug.  Returns HTTP 404 if not found.

``DELETE /v1/prompts/{namespace}/{name}``
    Delete a prompt and all its associated versions, tags, and branches.
    Returns HTTP 404 if not found, HTTP 204 on success.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.prompts import PromptCreate, PromptResponse

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _to_response(prompt) -> PromptResponse:
    """Convert a ``Prompt`` domain object to its API response schema."""
    return PromptResponse(**prompt.model_dump())


@router.get("", response_model=list[PromptResponse])
def list_prompts(
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
    namespace: str | None = None,
    q: str | None = Query(None, description="Full-text search query"),
    tag: str | None = Query(None, description="Filter by tag"),
    model: str | None = Query(None, description="Filter by model hint"),
    visibility: str | None = Query(None, description="Filter by visibility"),
) -> list[PromptResponse]:
    """List prompts, optionally filtered by namespace, tag, model hint, or visibility."""
    if namespace is not None:
        try:
            store.check_namespace_access(namespace, cert_token)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    if q:
        prompts = store.search_prompts(
            q,
            namespace=namespace,
            tag=tag,
            model=model,
            visibility=visibility,
            cert_token=cert_token,
        )
    else:
        prompts = store.list_prompts(namespace, tag=tag, model=model, visibility=visibility)
    return [_to_response(p) for p in prompts]


@router.post("", response_model=PromptResponse, status_code=201)
def create_prompt(
    body: PromptCreate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> PromptResponse:
    """Create a new prompt in the given namespace."""
    try:
        store.check_namespace_access(body.namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if store.get_prompt(body.namespace, body.name):
        raise HTTPException(status_code=409, detail="Prompt already exists")
    prompt = store.create_prompt(
        body.namespace,
        body.name,
        body.description,
        tags=body.tags,
        model_hints=body.model_hints,
        license=body.license,
        visibility=body.visibility,
        variables=body.variables,
    )
    return _to_response(prompt)


@router.get("/{namespace}/{name}", response_model=PromptResponse)
def get_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> PromptResponse:
    """Return a single prompt by namespace and name."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return _to_response(prompt)


@router.delete("/{namespace}/{name}", status_code=204)
def delete_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Delete a prompt and all its versions."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    store.delete_prompt(prompt.id)
