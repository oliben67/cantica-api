# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class DiffRequest(BaseModel):
    ref1: str
    ref2: str


class DiffResponse(BaseModel):
    diff: str
    ref1: str
    ref2: str
    namespace: str
    name: str
