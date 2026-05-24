# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.models import VariableSchema


class VersionCreate(BaseModel):
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
