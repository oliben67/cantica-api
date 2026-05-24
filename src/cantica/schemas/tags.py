# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class TagCreate(BaseModel):
    name: str
    sha: str


class TagResponse(BaseModel):
    name: str
    prompt_id: str
    sha: str
    created_at: datetime
