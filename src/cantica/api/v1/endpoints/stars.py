# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.stars import StarResponse

router = APIRouter(prefix="/prompts", tags=["stars"])


def _to_response(star) -> StarResponse:
    return StarResponse(**star.model_dump())


@router.post("/{namespace}/{name}/star", response_model=StarResponse, status_code=201)
def star_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    user: UserDep,
) -> StarResponse:
    try:
        star = store.star_prompt(namespace, name, user["id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(star)


@router.delete("/{namespace}/{name}/star", status_code=204)
def unstar_prompt(
    namespace: str,
    name: str,
    store: StoreDep,
    user: UserDep,
) -> None:
    try:
        store.unstar_prompt(namespace, name, user["id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{namespace}/{name}/stargazers", response_model=list[StarResponse])
def list_stargazers(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
) -> list[StarResponse]:
    try:
        stars = store.list_stargazers(namespace, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_to_response(s) for s in stars]
