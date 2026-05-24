"""
Pydantic schemas for fork endpoints.

``ForkCreate``    — body for ``POST /v1/prompts/{ns}/{name}/fork``; requires
                    ``dest_namespace`` and ``dest_name``, with ``branch``
                    defaulting to ``"main"``.

``ForkResponse``  — lineage record containing the ``source_slug``,
                    ``source_sha`` (head SHA at the time of forking),
                    ``fork_slug``, and ``created_at``.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class ForkCreate(BaseModel):
    """Request body for forking a prompt into a new namespace."""

    dest_namespace: str
    dest_name: str
    branch: str = "main"


class ForkResponse(BaseModel):
    """Fork lineage record returned after a successful fork."""

    id: str
    source_slug: str
    source_sha: str
    fork_slug: str
    created_at: datetime
