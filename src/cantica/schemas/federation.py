"""
Pydantic request/response schemas for federation endpoints.

``FederationPeerCreate``    — body for ``POST /v1/federation/peers``.
``FederationPeerResponse``  — single peer record returned by the management API.
``FederatedResult``         — per-peer search/list result with prompt list and optional error.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.schemas.prompts import PromptResponse


class FederationPeerCreate(BaseModel):
    """Request body for registering a new federation peer."""

    name: str
    url: str
    api_key: str | None = None


class FederationPeerResponse(BaseModel):
    """Federation peer record returned by the management API."""

    id: str
    name: str
    url: str
    api_key: str | None
    added_at: datetime


class FederatedResult(BaseModel):
    """Prompts fetched from one peer, with attribution and optional error."""

    peer_id: str
    peer_name: str
    peer_url: str
    prompts: list[PromptResponse]
    error: str | None = None
