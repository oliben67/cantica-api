"""
Domain models package.  Re-exports every model class from ``cantica.models.prompt``
so callers can use ``from cantica.models import Prompt, Version, ...``.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

from .prompt import (
    Branch,
    Collection,
    Comment,
    Federation,
    FederationMember,
    FederationPeer,
    Fork,
    Namespace,
    NamespaceCert,
    Prompt,
    PromptSource,
    ServerIdentity,
    Star,
    Tag,
    VariableSchema,
    Version,
    Visibility,
    Webhook,
)

__all__ = [
    "Branch",
    "Collection",
    "Comment",
    "Federation",
    "FederationMember",
    "FederationPeer",
    "Fork",
    "Namespace",
    "NamespaceCert",
    "Prompt",
    "PromptSource",
    "ServerIdentity",
    "Star",
    "Tag",
    "VariableSchema",
    "Version",
    "Visibility",
    "Webhook",
]
