# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class CommentCreate(BaseModel):
    body: str
    version_sha: str | None = None


class CommentResponse(BaseModel):
    id: str
    prompt_id: str
    version_sha: str | None
    author: str
    body: str
    created_at: datetime
