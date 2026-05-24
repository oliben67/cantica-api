"""
FastAPI endpoints for branch management, rollback, and merge operations.

Router prefix: ``/v1/prompts``   Tag: ``branches``

Endpoints
---------
``GET  /v1/prompts/{namespace}/{name}/branches``
    List all branches for a prompt, including each branch's current head SHA.

``POST /v1/prompts/{namespace}/{name}/branches``
    Create a new branch starting at a given SHA.  Body: ``BranchCreate``
    (``name``, ``from_sha``).  Returns HTTP 404 if the prompt or SHA is not
    found.

``POST /v1/prompts/{namespace}/{name}/rollback``
    Reset a branch head to a past ref (SHA, tag, or branch name).
    Body: ``RollbackRequest`` (``ref``, ``branch``).  This is a non-destructive
    operation — history is preserved; only the branch pointer moves.

``POST /v1/prompts/{namespace}/{name}/merge``
    Fast-forward merge one branch into another.  Body: ``MergeRequest``
    (``from_branch``, ``into_branch``).  Returns HTTP 409 if a fast-forward
    merge is not possible (diverged histories).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.branches import BranchCreate, BranchResponse
from cantica.schemas.merge import MergeRequest, MergeResponse, RollbackRequest
from cantica.schemas.versions import VersionResponse

router = APIRouter(prefix="/prompts", tags=["branches"])


def _to_response(branch) -> BranchResponse:
    """Convert a ``Branch`` domain object to its API response schema."""
    return BranchResponse(**branch.model_dump())


@router.get("/{namespace}/{name}/branches", response_model=list[BranchResponse])
def list_branches(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> list[BranchResponse]:
    """List all branches of a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    cert_token: CertTokenDep = None,
) -> BranchResponse:
    """Create a new branch pointing to the given commit SHA."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    cert_token: CertTokenDep = None,
) -> VersionResponse:
    """Roll a branch back to a previous ref (tag, SHA, or branch name)."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    cert_token: CertTokenDep = None,
) -> MergeResponse:
    """Merge one branch into another, fast-forwarding the target branch head."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        version = store.merge(namespace, name, body.from_branch, body.into_branch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MergeResponse(**version.model_dump())
