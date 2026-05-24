"""
FastAPI endpoints for curated prompt collections.

Router prefix: ``/v1/collections``   Tag: ``collections``

A collection is a named, ordered list of prompts owned by a namespace.  It
works like a playlist or a curated registry category.  Items are added and
removed individually; the collection itself stores only lightweight membership
records with timestamps.

Endpoints
---------
``POST   /v1/collections``
    Create a new collection.  Body: ``CollectionCreate`` (``namespace``,
    ``name``, ``description``).  Returns HTTP 409 if the collection already
    exists.

``GET    /v1/collections``
    List collections.  Optionally filter by ``namespace`` query parameter.

``GET    /v1/collections/{namespace}/{name}``
    Retrieve a collection with its full item list (``CollectionDetail``
    embeds each prompt's ``PromptResponse``).  Returns HTTP 404 if not found.

``DELETE /v1/collections/{namespace}/{name}``
    Delete a collection and its membership records.  Returns HTTP 404 if not
    found, HTTP 204 on success.

``POST   /v1/collections/{namespace}/{name}/items``
    Add a prompt to a collection.  Body: ``CollectionItemAdd`` (``prompt_slug``
    in ``"namespace/name"`` format).  Idempotent — silently no-ops if the
    prompt is already a member.

``DELETE /v1/collections/{namespace}/{name}/items/{prompt_namespace}/{prompt_name}``
    Remove a specific prompt from a collection.  Returns HTTP 404 if the
    collection is not found.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.collections import (
    CollectionCreate,
    CollectionDetail,
    CollectionItemAdd,
    CollectionResponse,
)
from cantica.schemas.prompts import PromptResponse

router = APIRouter(prefix="/collections", tags=["collections"])


def _to_response(coll) -> CollectionResponse:
    """Convert a ``Collection`` domain object to its API response schema."""
    return CollectionResponse(**coll.model_dump())


def _prompt_to_response(p) -> PromptResponse:
    """Convert a ``Prompt`` domain object to its API response schema."""
    return PromptResponse(**p.model_dump())


@router.post("", response_model=CollectionResponse, status_code=201)
def create_collection(
    body: CollectionCreate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> CollectionResponse:
    """Create a new collection in the given namespace."""
    try:
        store.check_namespace_access(body.namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        coll = store.create_collection(body.namespace, body.name, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(coll)


@router.get("", response_model=list[CollectionResponse])
def list_collections(
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
    namespace: str | None = Query(None),
) -> list[CollectionResponse]:
    """List all collections, optionally filtered by namespace."""
    if namespace is not None:
        try:
            store.check_namespace_access(namespace, cert_token)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [_to_response(c) for c in store.list_collections(namespace)]


@router.get("/{namespace}/{name}", response_model=CollectionDetail)
def get_collection(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> CollectionDetail:
    """Return a collection with its full list of prompts."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    coll = store.get_collection(namespace, name)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    try:
        items = store.list_collection_items(namespace, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CollectionDetail(
        **coll.model_dump(),
        items=[_prompt_to_response(p) for p in items],
    )


@router.delete("/{namespace}/{name}", status_code=204)
def delete_collection(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Delete a collection (does not delete the prompts it contains)."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not store.delete_collection(namespace, name):
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("/{namespace}/{name}/items", status_code=204)
def add_item(
    namespace: str,
    name: str,
    body: CollectionItemAdd,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Add a prompt to a collection."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        store.add_to_collection(namespace, name, body.prompt_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{namespace}/{name}/items/{prompt_namespace}/{prompt_name}", status_code=204)
def remove_item(
    namespace: str,
    name: str,
    prompt_namespace: str,
    prompt_name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Remove a prompt from a collection."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        store.remove_from_collection(namespace, name, f"{prompt_namespace}/{prompt_name}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
