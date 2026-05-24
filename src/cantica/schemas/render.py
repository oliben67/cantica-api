"""
Pydantic schemas for the render endpoint.

``RenderRequest``   — body for ``POST /v1/render``; requires a ``slug`` in
                      ``"namespace/name"`` format, an optional ``ref``
                      (defaults to ``"latest"``), and an optional ``variables``
                      dict mapping placeholder names to replacement values.

``RenderResponse``  — returned rendered content string along with the resolved
                      ``slug``, ``ref``, and ``sha`` so callers can cache or
                      audit the exact version that was rendered.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class RenderRequest(BaseModel):
    """Request body for rendering a prompt version with variable substitution."""

    slug: str
    ref: str = "latest"
    variables: dict[str, str] = {}


class RenderResponse(BaseModel):
    """Rendered prompt content and the resolved version metadata."""

    content: str
    slug: str
    ref: str
    sha: str
