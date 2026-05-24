# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.collections import (
    CollectionCreate,
    CollectionDetail,
    CollectionItemAdd,
    CollectionResponse,
)
from cantica.schemas.prompts import PromptResponse

router = APIRouter(prefix="/collections", tags=["collections"])


def _to_response(coll) -> CollectionResponse:
    return CollectionResponse(**coll.model_dump())


def _prompt_to_response(p) -> PromptResponse:
    return PromptResponse(**p.model_dump())


@router.post("", response_model=CollectionResponse, status_code=201)
def create_collection(
    body: CollectionCreate,
    store: StoreDep,
    _user: UserDep,
) -> CollectionResponse:
    try:
        coll = store.create_collection(body.namespace, body.name, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(coll)


@router.get("", response_model=list[CollectionResponse])
def list_collections(
    store: StoreDep,
    _user: UserDep,
    namespace: str | None = Query(None),
) -> list[CollectionResponse]:
    return [_to_response(c) for c in store.list_collections(namespace)]


@router.get("/{namespace}/{name}", response_model=CollectionDetail)
def get_collection(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
) -> CollectionDetail:
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
) -> None:
    if not store.delete_collection(namespace, name):
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("/{namespace}/{name}/items", status_code=204)
def add_item(
    namespace: str,
    name: str,
    body: CollectionItemAdd,
    store: StoreDep,
    _user: UserDep,
) -> None:
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
) -> None:
    try:
        store.remove_from_collection(namespace, name, f"{prompt_namespace}/{prompt_name}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
