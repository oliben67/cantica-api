"""
Pydantic schemas for API token (authentication) endpoints.

``TokenCreate``    — body for ``POST /v1/tokens``; only the human-readable
                     ``name`` is required.

``TokenResponse``  — returned once at token creation; includes the plaintext
                     ``key`` (shown exactly once, never stored).

``TokenInfo``      — returned by ``GET /v1/tokens``; omits the raw key and
                     includes ``last_used_at`` for audit purposes.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class TokenCreate(BaseModel):
    """Request body for creating a new API token."""

    name: str


class TokenResponse(BaseModel):
    """Response returned once at token creation; includes the plaintext key."""

    id: str
    name: str
    key: str  # raw key — shown exactly once at creation
    created_at: datetime


class TokenInfo(BaseModel):
    """Token metadata returned by the list endpoint (raw key omitted)."""

    id: str
    name: str
    created_at: datetime
    last_used_at: datetime | None
