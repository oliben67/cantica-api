# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class ForkCreate(BaseModel):
    dest_namespace: str
    dest_name: str
    branch: str = "main"


class ForkResponse(BaseModel):
    id: str
    source_slug: str
    source_sha: str
    fork_slug: str
    created_at: datetime
