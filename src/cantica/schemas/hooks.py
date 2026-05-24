"""
Pydantic schemas for webhook endpoints.

``WebhookCreate``    — body for ``POST /v1/hooks``; requires the target ``url``,
                       an HMAC ``secret``, an ``events`` list (defaults to
                       ``["version.created"]``), and an optional ``namespace``
                       filter.

``WebhookResponse``  — returned by create and list endpoints; omits the ``secret``
                       field.  ``created_at`` is serialised as an ISO 8601 string
                       (not a ``datetime`` object, for compatibility with the ORM
                       layer).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class WebhookCreate(BaseModel):
    """Request body for registering a new webhook."""

    url: str
    events: list[str] = ["version.created"]
    secret: str
    namespace: str | None = None


class WebhookResponse(BaseModel):
    """Webhook record returned by list and create endpoints."""

    id: str
    url: str
    events: list[str]
    namespace: str | None
    created_at: str
