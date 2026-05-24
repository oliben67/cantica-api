"""
Pydantic schemas for comment endpoints.

``CommentCreate``    — body for ``POST /v1/prompts/{ns}/{name}/comments``;
                       requires ``body`` text and an optional ``version_sha``
                       to pin the comment to a specific version.

``CommentResponse``  — full comment record including ``id``, ``prompt_id``,
                       ``version_sha`` (nullable), ``author``, ``body``, and
                       ``created_at``.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class CommentCreate(BaseModel):
    """Request body for adding a comment to a prompt or version."""

    body: str
    version_sha: str | None = None


class CommentResponse(BaseModel):
    """Comment record returned by list and add endpoints."""

    id: str
    prompt_id: str
    version_sha: str | None
    author: str
    body: str
    created_at: datetime
