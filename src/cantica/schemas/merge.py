# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.schemas.versions import VersionResponse


class MergeRequest(BaseModel):
    from_branch: str
    into_branch: str = "main"


class RollbackRequest(BaseModel):
    ref: str
    branch: str = "main"


class MergeResponse(VersionResponse):
    pass
