"""
Pydantic schemas for collection endpoints.

``CollectionCreate``    — body for ``POST /v1/collections``; requires
                          ``namespace``, ``name``, and optional ``description``.

``CollectionResponse``  — lightweight collection record (no items list).

``CollectionItemAdd``   — body for ``POST /v1/collections/{ns}/{name}/items``;
                          ``prompt_slug`` must be in ``"namespace/name"`` format.

``CollectionDetail``    — extended response for ``GET /v1/collections/{ns}/{name}``
                          that embeds the full ``items`` list of ``PromptResponse``
                          objects, ordered by when they were added.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.schemas.prompts import PromptResponse


class CollectionCreate(BaseModel):
    """Request body for creating a new collection."""

    namespace: str
    name: str
    description: str = ""


class CollectionResponse(BaseModel):
    """Collection metadata returned by list and create endpoints."""

    id: str
    namespace: str
    name: str
    description: str
    created_at: datetime


class CollectionItemAdd(BaseModel):
    """Request body for adding a prompt to a collection."""

    prompt_slug: str


class CollectionDetail(BaseModel):
    """Collection metadata together with its full list of prompts."""

    id: str
    namespace: str
    name: str
    description: str
    created_at: datetime
    items: list[PromptResponse]
