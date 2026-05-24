# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.diff import DiffRequest, DiffResponse

router = APIRouter(prefix="/prompts", tags=["diff"])


@router.post("/{namespace}/{name}/diff", response_model=DiffResponse)
def diff_versions(
    namespace: str,
    name: str,
    body: DiffRequest,
    store: StoreDep,
    _user: UserDep,
) -> DiffResponse:
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    try:
        v1 = store.resolve(namespace, name, body.ref1)
        v2 = store.resolve(namespace, name, body.ref2)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DiffResponse(
        diff=store.diff(v1.sha, v2.sha),
        ref1=body.ref1,
        ref2=body.ref2,
        namespace=namespace,
        name=name,
    )
