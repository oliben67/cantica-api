"""
FastAPI endpoints for the Cantica federation membership protocol.

Protocol endpoints (called by remote servers)
---------------------------------------------
``POST /v1/federate``
    Inbound federation action: join, leave, notify, eject.  The request is
    RSA-PSS signed by the sender; the signature is verified before processing.

``POST /v1/federate/sync``
    Non-founder sends hybrid-encrypted members table; founder reconciles and
    returns the canonical table encrypted with the sender's public key.

Management endpoints (called by the local operator)
----------------------------------------------------
``GET  /v1/identity``
    Return this server's RSA public key (generated on first call).

``GET  /v1/federations``
    List all federations this server belongs to.

``POST /v1/federations``
    Create a new federation (this server becomes the founder).

``GET  /v1/federations/{id}/members``
    List accepted members of a federation.

``DELETE /v1/federations/{id}/members/{mid}``
    Eject a member (founder only; sends signed eject notice to remaining members).

``POST /v1/federations/{id}/join``
    Send a join request to the founding server.

``POST /v1/federations/{id}/leave``
    Send a leave notice to the founding server and remove local membership.

``POST /v1/federations/{id}/sync``
    Sync local members table with the founding server.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import json

# Third party imports:
import httpx
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.core.federation_crypto import (
    decrypt_from,
    encrypt_for,
    sign_message,
    verify_signature,
)
from cantica.schemas.federate import (
    FederateRequest,
    FederateResponse,
    FederationCreate,
    FederationMemberResponse,
    FederationResponse,
    JoinRequest,
    ServerIdentityResponse,
    SyncRequest,
    SyncResponse,
)

router = APIRouter(tags=["federate"])


# ── Helpers ────────────────────────────────────────────────────────────────


def _canonicalise(req: FederateRequest) -> bytes:
    """Serialise a FederateRequest to a canonical byte string for signing/verification.

    Excludes the ``signature`` field and sorts keys to produce a deterministic representation.
    """
    data = req.model_dump(exclude={"signature"})
    return json.dumps(data, sort_keys=True).encode()


def _member_response(m) -> FederationMemberResponse:  # type: ignore[no-untyped-def]
    """Convert a FederationMember domain model to a response schema."""
    return FederationMemberResponse(
        id=m.id,
        federation_id=m.federation_id,
        public_key=m.public_key,
        federate_url=m.federate_url,
        is_accepted=m.is_accepted,
        joined_at=m.joined_at,
        updated_at=m.updated_at,
    )


# ── Identity ───────────────────────────────────────────────────────────────


@router.get("/identity", response_model=ServerIdentityResponse)
def get_identity(store: StoreDep, _user: UserDep) -> ServerIdentityResponse:
    """Return this server's RSA public key, generating the key pair if needed."""
    identity = store.get_or_create_identity()
    return ServerIdentityResponse(
        public_key_pem=identity.public_key_pem, created_at=identity.created_at
    )


# ── Federation management ──────────────────────────────────────────────────


@router.get("/federations", response_model=list[FederationResponse])
def list_federations(store: StoreDep, _user: UserDep) -> list[FederationResponse]:
    """List all federations this server belongs to."""
    feds = store.list_federations()
    result = []
    for f in feds:
        members = store.list_federation_members(f.id, accepted_only=True)
        result.append(
            FederationResponse(
                id=f.id,
                name=f.name,
                founding_key=f.founding_key,
                is_founder=f.is_founder,
                created_at=f.created_at,
                member_count=len(members),
            )
        )
    return result


@router.post("/federations", response_model=FederationResponse, status_code=201)
def create_federation(
    body: FederationCreate, store: StoreDep, _user: UserDep
) -> FederationResponse:
    """Create a new federation; this server becomes the founding member."""
    # Check for duplicate name
    existing = store.get_federation_by_name(body.name)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Federation {body.name!r} already exists")
    fed, _member = store.create_federation(body.name)
    members = store.list_federation_members(fed.id, accepted_only=True)
    return FederationResponse(
        id=fed.id,
        name=fed.name,
        founding_key=fed.founding_key,
        is_founder=fed.is_founder,
        created_at=fed.created_at,
        member_count=len(members),
    )


@router.get(
    "/federations/{federation_id}/members", response_model=list[FederationMemberResponse]
)
def list_members(
    federation_id: str, store: StoreDep, _user: UserDep
) -> list[FederationMemberResponse]:
    """Return all accepted members of *federation_id*."""
    fed = store.get_federation(federation_id)
    if fed is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    members = store.list_federation_members(federation_id, accepted_only=True)
    return [_member_response(m) for m in members]


@router.delete("/federations/{federation_id}/members/{member_id}", status_code=204)
def eject_member(
    federation_id: str, member_id: str, store: StoreDep, _user: UserDep
) -> None:
    """Eject a member (founder only).  Sends a signed eject notice to all remaining members."""
    fed = store.get_federation(federation_id)
    if fed is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    if not fed.is_founder:
        raise HTTPException(status_code=403, detail="Only the founder can eject members")
    if not store.remove_federation_member(member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    # Best-effort: notify remaining members of the ejection
    identity = store.get_or_create_identity()
    remaining = store.list_federation_members(federation_id, accepted_only=True)
    for member in remaining:
        if not member.federate_url:
            continue
        payload = FederateRequest(
            federation_id=federation_id,
            public_key=identity.public_key_pem,
            federate_url="",
            is_accepted=False,
            action="eject",
            target_key=None,
            signature="",
        )
        canonical = _canonicalise(payload)
        sig = store.sign_federation_message(canonical)
        payload = FederateRequest(
            federation_id=federation_id,
            public_key=identity.public_key_pem,
            federate_url="",
            is_accepted=False,
            action="eject",
            target_key=None,
            signature=sig,
        )
        try:
            import asyncio  # noqa: PLC0415

            asyncio.get_event_loop().run_until_complete(
                _send_federate(member.federate_url, payload)
            )
        except Exception:  # noqa: BLE001
            pass  # best-effort


async def _send_federate(url: str, payload: FederateRequest) -> None:
    """POST a FederateRequest to *url* asynchronously."""
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json=payload.model_dump())


# ── Join ───────────────────────────────────────────────────────────────────


@router.post("/federations/{federation_id}/join", response_model=FederateResponse)
async def join_federation(
    federation_id: str, body: JoinRequest, store: StoreDep, _user: UserDep
) -> FederateResponse:
    """Send a join request to the founding server at *body.founding_url*."""
    identity = store.get_or_create_identity()
    payload = FederateRequest(
        federation_id=federation_id,
        public_key=identity.public_key_pem,
        federate_url=body.founding_url,
        is_accepted=True,
        action="join",
        signature="",
    )
    canonical = _canonicalise(payload)
    sig = store.sign_federation_message(canonical)
    payload = FederateRequest(
        federation_id=federation_id,
        public_key=identity.public_key_pem,
        federate_url=body.founding_url,
        is_accepted=True,
        action="join",
        signature=sig,
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(body.founding_url, json=payload.model_dump())
        resp.raise_for_status()
        data = resp.json()
        ok = data.get("ok", False)
        if ok:
            # Persist the federation locally (if not already known)
            existing = store.get_federation(federation_id)
            if existing is None:
                # We don't have the federation yet; create a placeholder
                # (founder will sync canonical state later)
                store.session.execute(
                    __import__("sqlalchemy.dialects.sqlite", fromlist=["insert"]).insert(
                        __import__(
                            "cantica.orm.tables", fromlist=["FederationOrm"]
                        ).FederationOrm
                    ).values(
                        id=federation_id,
                        name=data.get("federation_name", "unknown"),
                        founding_key_enc=store._fed_enc_key and "",
                        created_at=__import__(
                            "cantica.services.version_store",
                            fromlist=["_iso", "_utcnow"],
                        )._iso(
                            __import__(
                                "cantica.services.version_store",
                                fromlist=["_utcnow"],
                            )._utcnow()
                        ),
                    ).on_conflict_do_nothing()
                )
                store.session.commit()
            # Add ourselves as a member
            store.add_federation_member(
                federation_id,
                identity.public_key_pem,
                body.founding_url,
                is_accepted=True,
            )
        return FederateResponse(ok=ok, message=data.get("message", ""))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach founding server: {exc}") from exc


# ── Leave ──────────────────────────────────────────────────────────────────


@router.post("/federations/{federation_id}/leave", response_model=FederateResponse)
async def leave_federation(
    federation_id: str, store: StoreDep, _user: UserDep
) -> FederateResponse:
    """Send a leave notice to all known members and remove local membership."""
    fed = store.get_federation(federation_id)
    if fed is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    identity = store.get_or_create_identity()
    members = store.list_federation_members(federation_id, accepted_only=True)
    payload_base = FederateRequest(
        federation_id=federation_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="leave",
        signature="",
    )
    canonical = _canonicalise(payload_base)
    sig = store.sign_federation_message(canonical)
    leave_payload = FederateRequest(
        federation_id=federation_id,
        public_key=identity.public_key_pem,
        federate_url="",
        is_accepted=False,
        action="leave",
        signature=sig,
    )
    # Notify all members (best-effort)
    errors = []
    for member in members:
        if not member.federate_url or member.public_key == identity.public_key_pem:
            continue
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(member.federate_url, json=leave_payload.model_dump())
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    # Remove ourselves from the federation locally
    our_membership = store.get_member_by_key(federation_id, identity.public_key_pem)
    if our_membership:
        store.remove_federation_member(our_membership.id)
    msg = "left" if not errors else f"left with errors: {'; '.join(errors)}"
    return FederateResponse(ok=True, message=msg)


# ── Sync ───────────────────────────────────────────────────────────────────


@router.post("/federations/{federation_id}/sync", response_model=SyncResponse)
async def sync_federation(
    federation_id: str, store: StoreDep, _user: UserDep
) -> SyncResponse:
    """Sync local member table with the founding server.

    Encrypts the local member list with the founder's public key, signs it,
    and sends it to the founder's ``/v1/federate/sync`` endpoint.
    """
    fed = store.get_federation(federation_id)
    if fed is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    if fed.is_founder:
        raise HTTPException(status_code=400, detail="Founder cannot sync with itself")
    identity = store.get_or_create_identity()
    members = store.list_federation_members(federation_id, accepted_only=False)
    table_json = json.dumps([m.model_dump(mode="json") for m in members])
    # Find the founder's federate URL from the member list
    founder_member = None
    for m in members:
        if m.public_key == fed.founding_key:
            founder_member = m
            break
    if founder_member is None or not founder_member.federate_url:
        raise HTTPException(status_code=400, detail="Founding server URL not known")
    # Encrypt table with founder's public key
    encrypted = encrypt_for(table_json.encode(), fed.founding_key)
    # Sign the encrypted blob
    sig = store.sign_federation_message(encrypted.encode())
    sync_req = SyncRequest(
        federation_id=federation_id,
        public_key=identity.public_key_pem,
        encrypted_table=encrypted,
        signature=sig,
    )
    founder_sync_url = founder_member.federate_url.rstrip("/") + "/sync"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(founder_sync_url, json=sync_req.model_dump())
        resp.raise_for_status()
        data = resp.json()
        return SyncResponse(
            encrypted_table=data["encrypted_table"],
            signature=data["signature"],
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not reach founding server: {exc}"
        ) from exc


# ── Protocol endpoints (inbound) ──────────────────────────────────────────


@router.post("/federate", response_model=FederateResponse)
def federate(req: FederateRequest, store: StoreDep, _user: UserDep) -> FederateResponse:
    """Inbound federation protocol handler.

    Verifies the sender's signature, then dispatches to the appropriate action
    handler (join, leave, notify, eject).
    """
    # Verify signature
    canonical = _canonicalise(req)
    if not verify_signature(canonical, req.signature, req.public_key):
        raise HTTPException(status_code=401, detail="Invalid signature")

    identity = store.get_or_create_identity()

    if req.action == "join":
        fed = store.get_federation(req.federation_id)
        if fed is None:
            raise HTTPException(status_code=404, detail="Federation not found")
        store.add_federation_member(
            req.federation_id, req.public_key, req.federate_url, is_accepted=True
        )
        members = store.list_federation_members(req.federation_id, accepted_only=True)
        return FederateResponse(
            ok=True,
            members=[_member_response(m) for m in members],
            message="joined",
        )

    if req.action == "leave":
        leaving_member = store.get_member_by_key(req.federation_id, req.public_key)
        if leaving_member:
            store.remove_federation_member(leaving_member.id)
        return FederateResponse(ok=True, message="removed")

    if req.action == "notify":
        # Update the member's record (URL or status)
        store.add_federation_member(
            req.federation_id, req.public_key, req.federate_url, is_accepted=req.is_accepted
        )
        return FederateResponse(ok=True, message="updated")

    if req.action == "eject":
        # Only accepted from the founding server
        fed = store.get_federation(req.federation_id)
        if fed is None:
            raise HTTPException(status_code=404, detail="Federation not found")
        if req.public_key != fed.founding_key:
            raise HTTPException(status_code=403, detail="Only the founder can eject members")
        target_key = req.target_key
        if target_key:
            target = store.get_member_by_key(req.federation_id, target_key)
            if target:
                store.remove_federation_member(target.id)
        elif req.public_key == identity.public_key_pem:
            # We are ejected
            our_member = store.get_member_by_key(req.federation_id, identity.public_key_pem)
            if our_member:
                store.remove_federation_member(our_member.id)
        return FederateResponse(ok=True, message="ejected")

    raise HTTPException(status_code=400, detail=f"Unknown action {req.action!r}")


@router.post("/federate/sync", response_model=SyncResponse)
def federate_sync(req: SyncRequest, store: StoreDep, _user: UserDep) -> SyncResponse:
    """Founder-only: reconcile a submitted member table and return the canonical list.

    The sender must be a known member of the federation.  The encrypted table is
    decrypted with this server's private key, reconciled, and re-encrypted with
    the sender's public key.
    """
    fed = store.get_federation(req.federation_id)
    if fed is None:
        raise HTTPException(status_code=404, detail="Federation not found")
    if not fed.is_founder:
        raise HTTPException(status_code=403, detail="Only the founder can handle sync requests")

    # Verify signature over the encrypted_table bytes
    if not verify_signature(
        req.encrypted_table.encode(), req.signature, req.public_key
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Decrypt the submitted table
    try:
        priv = store._read_federation_private_key()
        raw_json = decrypt_from(req.encrypted_table, priv)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {exc}") from exc

    submitted: list[dict] = json.loads(raw_json)
    canonical = store.reconcile_members_table(req.federation_id, submitted)

    # Re-encrypt canonical table with sender's public key
    canonical_json = json.dumps([m.model_dump(mode="json") for m in canonical])
    encrypted_canonical = encrypt_for(canonical_json.encode(), req.public_key)
    # Sign the plaintext canonical table
    sig = store.sign_federation_message(canonical_json.encode())
    return SyncResponse(encrypted_table=encrypted_canonical, signature=sig)
