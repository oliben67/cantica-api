"""
FastAPI endpoints for federation peer management and read-only cross-instance queries.

Router prefix: ``/v1/federation``   Tag: ``federation``

Federation is a read-only fan-out mechanism: a Cantica instance can register
remote peers and query them for prompts.  No data is written to peers.

Endpoints
---------
``GET    /v1/federation/peers``
    List all registered federation peers.

``POST   /v1/federation/peers``
    Register a new federation peer (name + URL + optional API key).

``DELETE /v1/federation/peers/{peer_id}``
    Remove a peer.  Returns 404 if not found, 204 on success.

``GET    /v1/federation/search``
    Fan-out a search query to all registered peers in parallel.
    Returns one ``FederatedResult`` per peer (prompts list + optional error).

``GET    /v1/federation/prompts``
    Fan-out a list-prompts request to all registered peers.
    Supports the same ``namespace``, ``tag``, ``model`` filters as the local
    ``/v1/prompts`` endpoint.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import asyncio

# Third party imports:
import httpx
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.federation import FederatedResult, FederationPeerCreate, FederationPeerResponse
from cantica.schemas.prompts import PromptResponse

router = APIRouter(prefix="/federation", tags=["federation"])


# ── Helpers ────────────────────────────────────────────────────────────────


async def _fetch_prompts(
    peer_id: str,
    peer_name: str,
    peer_url: str,
    api_key: str | None,
    params: dict,
) -> FederatedResult:
    """Fetch prompts from one peer, returning an error entry on failure."""
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    # Remove None-valued params so we don't send spurious query string keys.
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{peer_url}/v1/prompts", params=clean, headers=headers)
        resp.raise_for_status()
        raw: list[dict] = resp.json()
        prompts = [PromptResponse(**p) for p in raw]
        return FederatedResult(peer_id=peer_id, peer_name=peer_name, peer_url=peer_url, prompts=prompts)
    except Exception as exc:  # noqa: BLE001
        return FederatedResult(
            peer_id=peer_id, peer_name=peer_name, peer_url=peer_url,
            prompts=[], error=str(exc),
        )


# ── Peer management ────────────────────────────────────────────────────────


@router.get("/peers", response_model=list[FederationPeerResponse])
def list_peers(store: StoreDep, _user: UserDep) -> list[FederationPeerResponse]:
    """Return all registered federation peers."""
    return [FederationPeerResponse(**p.model_dump()) for p in store.list_federation_peers()]


@router.post("/peers", response_model=FederationPeerResponse, status_code=201)
def add_peer(body: FederationPeerCreate, store: StoreDep, _user: UserDep) -> FederationPeerResponse:
    """Register a new read-only federation peer."""
    peer = store.add_federation_peer(body.name, body.url, body.api_key)
    return FederationPeerResponse(**peer.model_dump())


@router.delete("/peers/{peer_id}", status_code=204)
def remove_peer(peer_id: str, store: StoreDep, _user: UserDep) -> None:
    """Remove a federation peer by ID."""
    if not store.remove_federation_peer(peer_id):
        raise HTTPException(status_code=404, detail="Peer not found")


# ── Read-only fan-out ──────────────────────────────────────────────────────


@router.get("/search", response_model=list[FederatedResult])
async def federated_search(
    store: StoreDep,
    _user: UserDep,
    q: str = Query(..., description="Full-text search query"),
    namespace: str | None = Query(None),
    tag: str | None = Query(None),
    model: str | None = Query(None),
    visibility: str | None = Query(None),
) -> list[FederatedResult]:
    """Fan-out a search query to all registered peers (read-only)."""
    peers = store.list_federation_peers()
    if not peers:
        return []
    params = {"q": q, "namespace": namespace, "tag": tag, "model": model, "visibility": visibility}
    tasks = [
        _fetch_prompts(p.id, p.name, p.url, p.api_key, params)
        for p in peers
    ]
    return list(await asyncio.gather(*tasks))


@router.get("/prompts", response_model=list[FederatedResult])
async def federated_list(
    store: StoreDep,
    _user: UserDep,
    namespace: str | None = Query(None),
    tag: str | None = Query(None),
    model: str | None = Query(None),
    visibility: str | None = Query(None),
) -> list[FederatedResult]:
    """Fan-out a list-prompts request to all registered peers (read-only)."""
    peers = store.list_federation_peers()
    if not peers:
        return []
    params = {"namespace": namespace, "tag": tag, "model": model, "visibility": visibility}
    tasks = [
        _fetch_prompts(p.id, p.name, p.url, p.api_key, params)
        for p in peers
    ]
    return list(await asyncio.gather(*tasks))
