"""
Pydantic schemas for branch endpoints.

``BranchCreate``    — body for ``POST /v1/prompts/{ns}/{name}/branches``;
                      requires a ``name`` and the ``from_sha`` the branch should
                      start at.

``BranchResponse``  — response returned for branch list and create endpoints;
                      includes the current ``head_sha`` and timestamps.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class BranchCreate(BaseModel):
    """Request body for creating a new branch."""

    name: str
    from_sha: str


class BranchResponse(BaseModel):
    """Branch record returned by list and create endpoints."""

    name: str
    prompt_id: str
    head_sha: str
    created_at: datetime
    updated_at: datetime
