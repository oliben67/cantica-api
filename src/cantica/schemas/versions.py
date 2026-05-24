"""
Pydantic request/response schemas for version endpoints.

``VersionCreate``   — body schema for ``POST /v1/prompts/{ns}/{name}/versions``.
                      When ``sha`` + ``created_at`` are both provided the server
                      uses ``import_version()`` to preserve the exact SHA (used
                      by push/pull sync).  Otherwise the server computes the SHA.

``VersionResponse`` — response schema returned by all version endpoints; mirrors
                      the ``Version`` domain model fields, including ``content``
                      (the full prompt text), ``tags`` (names of tags pointing at
                      this SHA), and the full commit metadata.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.models import VariableSchema


class VersionCreate(BaseModel):
    """Request body for committing a new version or importing an existing one."""

    content: str
    message: str
    author: str
    branch: str = "main"
    variables: list[VariableSchema] = []
    # Optional import fields — when all three are provided the server uses
    # import_version() so the SHA is preserved across instances.
    sha: str | None = None
    parent_sha: str | None = None
    created_at: datetime | None = None


class VersionResponse(BaseModel):
    """Version record returned by all version endpoints."""

    sha: str
    prompt_id: str
    branch: str
    parent_sha: str | None
    message: str
    author: str
    content: str
    variables: list[VariableSchema]
    tags: list[str]
    created_at: datetime
