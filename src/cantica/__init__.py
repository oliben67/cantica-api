"""
Cantica — versioned, community-driven AI prompt registry.

This is the top-level package.  It re-exports the core public surface so that
downstream code (CLI, API layer, third-party integrations) can import directly
from ``cantica`` without knowing the internal sub-package layout:

    from cantica import VersionStore, Prompt, BlobStore, parse_address

Key modules:
- ``cantica.services.version_store``  — ``VersionStore``, the single authoritative
  service for all data operations (prompts, versions, branches, tags, forks, etc.).
- ``cantica.services.blob_store``     — ``BlobStore``, git-style content-addressable
  blob storage (SHA-256 keyed files under ``<vault>/objects/``).
- ``cantica.services.template_engine``— ``TemplateEngine``, ``{{variable}}`` prompt
  rendering with schema validation and defaults.
- ``cantica.models``                  — Pydantic domain models (``Prompt``, ``Version``,
  ``Branch``, ``Tag``, ``Fork``, etc.).
- ``cantica.core.resolver``           — ``parse_address`` / ``PromptAddress`` for
  parsing ``namespace/name[@ref]`` and ``cantica://`` URIs.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

from .core.resolver import PromptAddress, parse_address
from .models import Branch, Namespace, Prompt, Tag, VariableSchema, Version, Visibility
from .services.blob_store import BlobStore
from .services.template_engine import TemplateEngine
from .services.version_store import VersionStore
from .shim import CanticaShim

__all__ = [
    "BlobStore",
    "Branch",
    "CanticaShim",
    "Namespace",
    "Prompt",
    "PromptAddress",
    "Tag",
    "TemplateEngine",
    "VariableSchema",
    "Version",
    "VersionStore",
    "Visibility",
    "parse_address",
]
