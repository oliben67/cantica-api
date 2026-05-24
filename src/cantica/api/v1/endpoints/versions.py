# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.versions import VersionCreate, VersionResponse

router = APIRouter(prefix="/prompts", tags=["versions"])


def _to_response(version) -> VersionResponse:
    return VersionResponse(**version.model_dump())


@router.get("/{namespace}/{name}/versions", response_model=list[VersionResponse])
def list_versions(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    branch: str = "main",
) -> list[VersionResponse]:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(v) for v in store.log(prompt.id, branch)]


@router.post("/{namespace}/{name}/versions", response_model=VersionResponse, status_code=201)
def commit_version(
    namespace: str,
    name: str,
    body: VersionCreate,
    store: StoreDep,
    _user: UserDep,
) -> VersionResponse:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if body.sha and body.created_at:
        try:
            version = store.import_version(
                prompt.id,
                body.sha,
                body.content,
                body.message,
                body.author,
                body.branch,
                body.parent_sha,
                body.created_at,
                body.variables,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        version = store.commit(
            prompt.id,
            body.content,
            body.message,
            body.author,
            branch=body.branch,
            variables=body.variables,
        )
    return _to_response(version)


@router.get("/{namespace}/{name}/versions/{ref}", response_model=VersionResponse)
def get_version_at_ref(
    namespace: str,
    name: str,
    ref: str,
    store: StoreDep,
    _user: UserDep,
) -> VersionResponse:
    try:
        version = store.resolve(namespace, name, ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(version)
