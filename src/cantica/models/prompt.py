# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# Third party imports:
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Visibility(StrEnum):
    public = "public"
    private = "private"
    unlisted = "unlisted"
    team = "team"


class VariableSchema(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    default: Any = None
    required: bool = False


class Prompt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    model_hints: list[str] = Field(default_factory=list)
    license: str = "MIT"
    visibility: Visibility = Visibility.public
    variables: list[VariableSchema] = Field(default_factory=list)
    star_count: int = 0
    fork_count: int = 0
    default_branch: str = "main"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def slug(self) -> str:
        return f"{self.namespace}/{self.name}"


class Version(BaseModel):
    sha: str
    prompt_id: str
    branch: str = "main"
    parent_sha: str | None = None
    message: str
    author: str
    content: str
    variables: list[VariableSchema] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    tags: list[str] = Field(default_factory=list)


class Tag(BaseModel):
    name: str
    prompt_id: str
    sha: str
    created_at: datetime = Field(default_factory=_utcnow)


class Branch(BaseModel):
    name: str
    prompt_id: str
    head_sha: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Fork(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_slug: str
    source_sha: str
    fork_slug: str
    created_at: datetime = Field(default_factory=_utcnow)


class Namespace(BaseModel):
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Star(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    prompt_id: str
    created_at: datetime = Field(default_factory=_utcnow)


class Comment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt_id: str
    version_sha: str | None = None
    author: str
    body: str
    created_at: datetime = Field(default_factory=_utcnow)


class Collection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Webhook(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    events: list[str] = Field(default_factory=lambda: ["version.created"])
    secret: str
    namespace: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
