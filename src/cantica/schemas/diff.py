"""
Pydantic schemas for the diff endpoint.

``DiffRequest``   — body for ``POST /v1/prompts/{ns}/{name}/diff``;
                    specifies ``ref1`` and ``ref2`` to compare.

``DiffResponse``  — returned unified diff string together with the echoed
                    ``ref1``, ``ref2``, ``namespace``, and ``name`` fields.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class DiffRequest(BaseModel):
    """Request body specifying the two refs to diff."""

    ref1: str
    ref2: str


class DiffResponse(BaseModel):
    """Unified diff between two prompt version refs."""

    diff: str
    ref1: str
    ref2: str
    namespace: str
    name: str
