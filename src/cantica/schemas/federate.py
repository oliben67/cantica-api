"""
Pydantic schemas for the federation membership protocol.

Endpoints: ``/v1/federate`` (inbound protocol) and ``/v1/federations`` (management).

Classes
-------
FederateRequest         — inbound protocol message (join/leave/notify/eject)
FederateResponse        — response to a protocol message
SyncRequest             — non-founder sends encrypted members table to founder
SyncResponse            — founder returns canonical encrypted+signed members table
FederationCreate        — body for POST /v1/federations
FederationResponse      — federation record returned by management API
FederationMemberResponse — member record returned by management API
ServerIdentityResponse  — this server's public key
JoinRequest             — body for POST /v1/federations/{id}/join
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class FederateRequest(BaseModel):
    """Inbound federation protocol message posted to ``/v1/federate`` by another server."""

    federation_id: str
    public_key: str  # sender's RSA public key (PEM)
    federate_url: str  # sender's /v1/federate endpoint URL
    is_accepted: bool  # True = join/notify, False = leave/eject
    action: str  # "join" | "leave" | "notify" | "eject"
    target_key: str | None = None  # for notify/eject: affected member's public key
    signature: str  # RSA-PSS sig over canonicalised request (all fields except this)


class FederateResponse(BaseModel):
    """Response body returned by the federation protocol endpoint."""

    ok: bool
    members: list[FederationMemberResponse] = []
    message: str = ""


class SyncRequest(BaseModel):
    """Non-founder sends hybrid-encrypted members table to the founding server."""

    federation_id: str
    public_key: str  # sender's public key (for signature verification)
    encrypted_table: str  # hybrid-encrypted JSON list of member records
    signature: str  # RSA-PSS sig over *encrypted_table* bytes


class SyncResponse(BaseModel):
    """Founder returns canonical members table encrypted with the sender's public key."""

    encrypted_table: str  # canonical table re-encrypted with sender's public key
    signature: str  # founder's RSA-PSS sig over the plaintext canonical table


class FederationCreate(BaseModel):
    """Request body for creating a new federation."""

    name: str


class FederationResponse(BaseModel):
    """Federation record returned by the management API."""

    id: str
    name: str
    founding_key: str
    is_founder: bool
    created_at: datetime
    member_count: int = 0


class FederationMemberResponse(BaseModel):
    """Federation member record returned by the management API."""

    id: str
    federation_id: str
    public_key: str
    federate_url: str
    is_accepted: bool
    joined_at: datetime
    updated_at: datetime


class ServerIdentityResponse(BaseModel):
    """This server's RSA public key identity."""

    public_key_pem: str
    created_at: datetime


class JoinRequest(BaseModel):
    """Body for ``POST /v1/federations/{id}/join`` — outbound join request to founding server."""

    founding_url: str  # URL of the founding server's /v1/federate endpoint
