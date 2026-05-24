# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class RenderRequest(BaseModel):
    slug: str
    ref: str = "latest"
    variables: dict[str, str] = {}


class RenderResponse(BaseModel):
    content: str
    slug: str
    ref: str
    sha: str
