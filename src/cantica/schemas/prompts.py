# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel, computed_field

# Local imports:
from cantica.models import VariableSchema, Visibility


class PromptCreate(BaseModel):
    namespace: str
    name: str
    description: str = ""
    tags: list[str] = []
    model_hints: list[str] = []
    license: str = "MIT"
    visibility: Visibility = Visibility.public
    variables: list[VariableSchema] = []


class PromptResponse(BaseModel):
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
        return f"{self.namespace}/{self.name}"
