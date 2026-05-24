"""
Pydantic request/response schemas for prompt endpoints.

``PromptCreate``    — body schema for ``POST /v1/prompts``.
``PromptResponse``  — response schema returned by all prompt endpoints; adds a
                      computed ``slug`` property (``"namespace/name"``).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel, computed_field

# Local imports:
from cantica.models import VariableSchema, Visibility


class PromptCreate(BaseModel):
    """Request body for creating a new prompt."""

    namespace: str
    name: str
    description: str = ""
    tags: list[str] = []
    model_hints: list[str] = []
    license: str = "MIT"
    visibility: Visibility = Visibility.public
    variables: list[VariableSchema] = []


class PromptResponse(BaseModel):
    """Prompt record returned by all prompt endpoints."""

    id: str
    namespace: str
    name: str
    description: str
    tags: list[str]
    model_hints: list[str]
    license: str
    visibility: Visibility
    variables: list[VariableSchema]
    star_count: int
    fork_count: int
    default_branch: str
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        """Return the ``namespace/name`` slug for this prompt."""
        return f"{self.namespace}/{self.name}"
