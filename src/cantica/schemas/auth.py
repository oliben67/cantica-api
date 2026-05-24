# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class TokenCreate(BaseModel):
    name: str


class TokenResponse(BaseModel):
    id: str
    name: str
    key: str  # raw key — shown exactly once at creation
    created_at: datetime


class TokenInfo(BaseModel):
    id: str
    name: str
    created_at: datetime
    last_used_at: datetime | None
