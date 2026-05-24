# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = ["version.created"]
    secret: str
    namespace: str | None = None


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    namespace: str | None
    created_at: str
