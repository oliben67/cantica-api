"""
Pydantic schemas for branch merge and rollback operations.

``MergeRequest``    — body for ``POST /v1/prompts/{ns}/{name}/merge``;
                      specifies ``from_branch`` and ``into_branch`` (defaults to
                      ``"main"``).

``RollbackRequest`` — body for ``POST /v1/prompts/{ns}/{name}/rollback``;
                      specifies the target ``ref`` and the ``branch`` whose head
                      should be moved (defaults to ``"main"``).

``MergeResponse``   — subclass of ``VersionResponse`` returned after a successful
                      merge; contains the full version record at the new branch
                      head.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.schemas.versions import VersionResponse


class MergeRequest(BaseModel):
    """Request body for merging one branch into another."""

    from_branch: str
    into_branch: str = "main"


class RollbackRequest(BaseModel):
    """Request body for rolling a branch back to a prior ref."""

    ref: str
    branch: str = "main"


class MergeResponse(VersionResponse):
    """Version record returned after a successful branch merge."""

    pass
