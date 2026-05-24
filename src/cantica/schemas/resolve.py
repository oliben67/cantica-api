"""
Pydantic schema for the URI-resolve endpoint.

``ResolveRequest``  — body for ``POST /v1/resolve``; requires a ``uri`` in any
                      accepted ``cantica://`` address form (see
                      ``core/resolver.py``) and an optional ``remote_url`` to
                      override the host derived from the URI when fetching from
                      a remote instance.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class ResolveRequest(BaseModel):
    """Request body for resolving a cantica:// URI to a version."""

    uri: str
    remote_url: str | None = None
