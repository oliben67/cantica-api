"""
Schemas package: Pydantic request/response models for the REST API.

Re-exports every request body and response schema so endpoint code can import
from ``cantica.schemas`` directly rather than from individual sub-modules.

Schema groups (and the endpoints they serve):
- ``auth``        — ``TokenCreate``, ``TokenResponse``, ``TokenInfo``
- ``branches``    — ``BranchCreate``, ``BranchResponse``
- ``collections`` — ``CollectionCreate``, ``CollectionResponse``, ``CollectionItemAdd``, ``CollectionDetail``
- ``comments``    — ``CommentCreate``, ``CommentResponse``
- ``diff``        — ``DiffRequest``, ``DiffResponse``
- ``forks``       — ``ForkCreate``, ``ForkResponse``
- ``hooks``       — ``WebhookCreate``, ``WebhookResponse``
- ``merge``       — ``MergeRequest``, ``RollbackRequest``, ``MergeResponse``
- ``prompts``     — ``PromptCreate``, ``PromptResponse``
- ``render``      — ``RenderRequest``, ``RenderResponse``
- ``resolve``     — ``ResolveRequest``
- ``stars``       — ``StarResponse``
- ``tags``        — ``TagCreate``, ``TagResponse``
- ``versions``    — ``VersionCreate``, ``VersionResponse``
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

from .auth import TokenCreate, TokenInfo, TokenResponse
from .branches import BranchCreate, BranchResponse
from .collections import CollectionCreate, CollectionDetail, CollectionItemAdd, CollectionResponse
from .comments import CommentCreate, CommentResponse
from .diff import DiffRequest, DiffResponse
from .forks import ForkCreate, ForkResponse
from .hooks import WebhookCreate, WebhookResponse
from .merge import MergeRequest, MergeResponse, RollbackRequest
from .prompts import PromptCreate, PromptResponse
from .render import RenderRequest, RenderResponse
from .resolve import ResolveRequest
from .stars import StarResponse
from .tags import TagCreate, TagResponse
from .versions import VersionCreate, VersionResponse

__all__ = [
    "BranchCreate",
    "BranchResponse",
    "CollectionCreate",
    "CollectionDetail",
    "CollectionItemAdd",
    "CollectionResponse",
    "CommentCreate",
    "CommentResponse",
    "DiffRequest",
    "DiffResponse",
    "ForkCreate",
    "ForkResponse",
    "MergeRequest",
    "MergeResponse",
    "PromptCreate",
    "PromptResponse",
    "RenderRequest",
    "RenderResponse",
    "ResolveRequest",
    "RollbackRequest",
    "StarResponse",
    "TagCreate",
    "TagResponse",
    "TokenCreate",
    "TokenInfo",
    "TokenResponse",
    "VersionCreate",
    "VersionResponse",
    "WebhookCreate",
    "WebhookResponse",
]
