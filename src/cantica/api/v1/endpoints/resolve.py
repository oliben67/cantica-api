# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.resolve import ResolveRequest
from cantica.schemas.versions import VersionResponse

router = APIRouter(tags=["resolve"])


@router.post("/resolve", response_model=VersionResponse)
def resolve_uri(
    body: ResolveRequest,
    store: StoreDep,
    _user: UserDep,
) -> VersionResponse:
    try:
        version = store.resolve_uri(body.uri, body.remote_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VersionResponse(**version.model_dump())
