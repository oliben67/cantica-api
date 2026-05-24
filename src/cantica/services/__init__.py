"""
Services package: core business-logic layer.

Re-exports the three primary service classes:

- ``BlobStore``       — content-addressable file storage (SHA-256 keyed)
- ``TemplateEngine``  — ``{{variable}}`` prompt rendering
- ``VersionStore``    — authoritative data-access service for all entities
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

from .blob_store import BlobStore
from .template_engine import TemplateEngine
from .version_store import VersionStore

__all__ = ["BlobStore", "TemplateEngine", "VersionStore"]
