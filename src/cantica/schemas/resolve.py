# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class ResolveRequest(BaseModel):
    uri: str
    remote_url: str | None = None
