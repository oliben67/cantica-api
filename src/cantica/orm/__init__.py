"""
ORM package: SQLAlchemy ``Base`` and all mapped table classes.

Re-exports ``Base`` (for ``metadata.create_all``) and every ``*Orm`` class so
that other modules can import from ``cantica.orm`` without knowing the internal
module split.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Local imports:
from cantica.orm.base import Base
from cantica.orm.tables import (
    ApiKeyOrm,
    BranchOrm,
    ForkOrm,
    NamespaceOrm,
    PromptOrm,
    TagOrm,
    VersionOrm,
)

__all__ = [
    "Base",
    "ApiKeyOrm",
    "BranchOrm",
    "ForkOrm",
    "NamespaceOrm",
    "PromptOrm",
    "TagOrm",
    "VersionOrm",
]
