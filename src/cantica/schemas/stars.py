"""
Pydantic schema for star endpoints.

``StarResponse``  — returned by ``POST /v1/prompts/{ns}/{name}/star`` and
                    ``GET /v1/prompts/{ns}/{name}/stargazers``; contains the
                    star record's ``id``, the starring ``namespace``, the
                    ``prompt_id``, and the ``created_at`` timestamp.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class StarResponse(BaseModel):
    """Star record returned by list and star endpoints."""

    id: str
    namespace: str
    prompt_id: str
    created_at: datetime
