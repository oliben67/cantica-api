# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class StarResponse(BaseModel):
    id: str
    namespace: str
    prompt_id: str
    created_at: datetime
