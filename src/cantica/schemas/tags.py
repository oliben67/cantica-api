"""
Pydantic schemas for tag endpoints.

``TagCreate``    — body for ``POST /v1/prompts/{ns}/{name}/tags``; requires the
                   tag ``name`` and the target ``sha``.

``TagResponse``  — response schema; includes the ``prompt_id``, ``name``,
                   ``sha``, and ``created_at`` timestamp.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class TagCreate(BaseModel):
    """Request body for creating a named tag."""

    name: str
    sha: str


class TagResponse(BaseModel):
    """Tag record returned by list and create endpoints."""

    name: str
    prompt_id: str
    sha: str
    created_at: datetime
