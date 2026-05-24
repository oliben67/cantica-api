# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.branches import BranchCreate, BranchResponse
from cantica.schemas.merge import MergeRequest, MergeResponse, RollbackRequest
from cantica.schemas.versions import VersionResponse

router = APIRouter(prefix="/prompts", tags=["branches"])


def _to_response(branch) -> BranchResponse:
    return BranchResponse(**branch.model_dump())


@router.get("/{namespace}/{name}/branches", response_model=list[BranchResponse])
def list_branches(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
) -> list[BranchResponse]:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(b) for b in store.list_branches(prompt.id)]


@router.post("/{namespace}/{name}/branches", response_model=BranchResponse, status_code=201)
def create_branch(
    namespace: str,
    name: str,
    body: BranchCreate,
    store: StoreDep,
    _user: UserDep,
) -> BranchResponse:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if not store.get_version(body.from_sha):
        raise HTTPException(status_code=404, detail="SHA not found")
    branch = store.create_branch(prompt.id, body.name, body.from_sha)
    return _to_response(branch)


@router.post("/{namespace}/{name}/rollback", response_model=VersionResponse)
def rollback_branch(
    namespace: str,
    name: str,
    body: RollbackRequest,
    store: StoreDep,
    _user: UserDep,
) -> VersionResponse:
    try:
        version = store.rollback(namespace, name, body.ref, body.branch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VersionResponse(**version.model_dump())


@router.post("/{namespace}/{name}/merge", response_model=MergeResponse)
def merge_branch(
    namespace: str,
    name: str,
    body: MergeRequest,
    store: StoreDep,
    _user: UserDep,
) -> MergeResponse:
    try:
        version = store.merge(namespace, name, body.from_branch, body.into_branch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MergeResponse(**version.model_dump())
