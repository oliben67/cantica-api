# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel

# Local imports:
from cantica.schemas.prompts import PromptResponse


class CollectionCreate(BaseModel):
    namespace: str
    name: str
    description: str = ""


class CollectionResponse(BaseModel):
    id: str
    namespace: str
    name: str
    description: str
    created_at: datetime


class CollectionItemAdd(BaseModel):
    prompt_slug: str


class CollectionDetail(BaseModel):
    id: str
    namespace: str
    name: str
    description: str
    created_at: datetime
    items: list[PromptResponse]
