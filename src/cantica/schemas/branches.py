# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class BranchCreate(BaseModel):
    name: str
    from_sha: str


class BranchResponse(BaseModel):
    name: str
    prompt_id: str
    head_sha: str
    created_at: datetime
    updated_at: datetime
