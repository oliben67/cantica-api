# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.tags import TagCreate, TagResponse

router = APIRouter(prefix="/prompts", tags=["tags"])


def _to_response(tag) -> TagResponse:
    return TagResponse(**tag.model_dump())


@router.get("/{namespace}/{name}/tags", response_model=list[TagResponse])
def list_tags(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
) -> list[TagResponse]:
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
) -> TagResponse:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if not store.get_version(body.sha):
        raise HTTPException(status_code=404, detail="SHA not found")
    tag = store.create_tag(prompt.id, body.name, body.sha)
    return _to_response(tag)
