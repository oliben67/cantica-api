# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.prompts import PromptCreate, PromptResponse

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _to_response(prompt) -> PromptResponse:
    return PromptResponse(**prompt.model_dump())


@router.get("", response_model=list[PromptResponse])
def list_prompts(
    store: StoreDep,
    _user: UserDep,
    namespace: str | None = None,
    q: str | None = Query(None, description="Full-text search query"),
    tag: str | None = Query(None, description="Filter by tag"),
    model: str | None = Query(None, description="Filter by model hint"),
    visibility: str | None = Query(None, description="Filter by visibility"),
) -> list[PromptResponse]:
    if q:
        prompts = store.search_prompts(
            q, namespace=namespace, tag=tag, model=model, visibility=visibility
        )
    else:
        prompts = store.list_prompts(namespace, tag=tag, model=model, visibility=visibility)
    return [_to_response(p) for p in prompts]


@router.post("", response_model=PromptResponse, status_code=201)
def create_prompt(
    body: PromptCreate,
    store: StoreDep,
    _user: UserDep,
) -> PromptResponse:
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
) -> PromptResponse:
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
) -> None:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    store.delete_prompt(prompt.id)
