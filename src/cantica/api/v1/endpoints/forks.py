# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.forks import ForkCreate, ForkResponse

router = APIRouter(prefix="/prompts", tags=["forks"])


def _to_response(fork) -> ForkResponse:
    return ForkResponse(**fork.model_dump())


@router.post("/{namespace}/{name}/fork", response_model=ForkResponse, status_code=201)
def fork_prompt(
    namespace: str,
    name: str,
    body: ForkCreate,
    store: StoreDep,
    _user: UserDep,
) -> ForkResponse:
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
) -> list[ForkResponse]:
    if not store.get_prompt(namespace, name):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(f) for f in store.list_forks(namespace, name)]
