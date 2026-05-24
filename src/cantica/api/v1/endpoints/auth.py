# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.core.security import generate_api_key
from cantica.schemas.auth import TokenCreate, TokenInfo, TokenResponse

router = APIRouter(prefix="/tokens", tags=["auth"])


@router.post("", response_model=TokenResponse, status_code=201)
def create_token(
    body: TokenCreate,
    store: StoreDep,
    _user: UserDep,
) -> TokenResponse:
    raw_key, key_hash = generate_api_key()
    token_id, created_at = store.create_api_key(body.name, key_hash)
    return TokenResponse(id=token_id, name=body.name, key=raw_key, created_at=created_at)


@router.get("", response_model=list[TokenInfo])
def list_tokens(
    store: StoreDep,
    _user: UserDep,
) -> list[TokenInfo]:
    return [
        TokenInfo(id=id_, name=name, created_at=ca, last_used_at=lua)
        for id_, name, ca, lua in store.list_api_keys()
    ]


@router.delete("/{token_id}", status_code=204)
def revoke_token(
    token_id: str,
    store: StoreDep,
    _user: UserDep,
) -> None:
    if not store.revoke_api_key(token_id):
        raise HTTPException(status_code=404, detail="Token not found")
