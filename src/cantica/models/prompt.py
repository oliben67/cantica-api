"""
Pydantic domain models for the Cantica prompt registry.

These are the canonical in-memory representations of every entity in the
system.  They are produced by ``VersionStore`` (which reads from the ORM layer)
and consumed by the API layer (serialised to JSON) and the CLI.  Neither the
FastAPI endpoints nor the CLI ever touch ORM objects directly.

Models
------
Visibility
    String enum: ``public``, ``private``, ``unlisted``, ``team``.

VariableSchema
    A typed variable declared in a prompt's schema (``name``, ``type``,
    ``description``, ``default``, ``required``).  Used by ``TemplateEngine``
    to validate render calls.

Prompt
    The top-level registry entry.  Identified by ``namespace/name`` (the
    ``slug`` property).  Carries metadata (``description``, ``tags``,
    ``model_hints``, ``license``, ``visibility``, ``variables``) plus
    aggregate counters (``star_count``, ``fork_count``).

Version
    An immutable commit record.  ``sha`` is a git-style commit hash
    (SHA-256 of ``"commit\\n<content_sha>\\n<parent_sha>\\n<author>\\n<message>
    \\n<created_at_iso>"``), **not** the content hash.  Content itself is
    stored separately in the ``BlobStore``; ``Version.content`` is populated
    at read time.

Tag        Named pointer to a version SHA (analogous to a git tag).
Branch     Mutable pointer to the ``head_sha`` of a version chain.
Fork       Lineage record linking a source prompt slug to its fork slug.
Namespace  User or organisation namespace; auto-created on first prompt write.
Star       Record of a namespace starring a prompt.
Comment    Threaded comment on a prompt, optionally pinned to a version SHA.
Collection Curated list of prompts under a namespace.
Webhook    HTTP endpoint registered to receive ``version.created`` events.
"""

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
    """Return the current UTC time as an aware datetime."""
    return datetime.now(UTC)


class Visibility(StrEnum):
    """Prompt visibility level controlling who can discover and read a prompt."""

    public = "public"
    private = "private"
    unlisted = "unlisted"
    team = "team"


class VariableSchema(BaseModel):
    """Typed variable declared in a prompt schema; used by ``TemplateEngine`` at render time."""

    name: str
    type: str = "string"
    description: str = ""
    default: Any = None
    required: bool = False


class PromptSource(BaseModel):
    """Attribution and scraping provenance for a prompt imported from an external source."""

    url: str
    repo: str | None = None
    author: str | None = None
    # SPDX license id of the *original* work — separate from Prompt.license
    license: str | None = None
    scraped_at: datetime | None = None


class Prompt(BaseModel):
    """Top-level registry entry identified by ``namespace/name`` (see ``slug`` property)."""

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
    source: PromptSource | None = None

    @property
    def slug(self) -> str:
        """Return the canonical ``namespace/name`` identifier."""
        return f"{self.namespace}/{self.name}"


class Version(BaseModel):
    """Immutable commit record; SHA is a git-style hash over the commit fields."""

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
    """Named pointer to a version SHA (analogous to a git tag)."""

    name: str
    prompt_id: str
    sha: str
    created_at: datetime = Field(default_factory=_utcnow)


class Branch(BaseModel):
    """Mutable pointer to the head SHA of a version chain."""

    name: str
    prompt_id: str
    head_sha: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Fork(BaseModel):
    """Lineage record linking a source prompt slug to its forked copy slug."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_slug: str
    source_sha: str
    fork_slug: str
    created_at: datetime = Field(default_factory=_utcnow)


class Namespace(BaseModel):
    """User or organisation namespace; auto-created on first prompt write."""

    name: str
    description: str = ""
    is_proprietary: bool = False
    encoded: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


class NamespaceCert(BaseModel):
    """Signed access certificate granting a holder read access to a proprietary namespace."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    granted_to: str
    issued_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    revoked: bool = False
    # token is only populated at issuance and never stored in the DB
    token: str | None = None


class Star(BaseModel):
    """Record that a namespace starred a prompt."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    prompt_id: str
    created_at: datetime = Field(default_factory=_utcnow)


class Comment(BaseModel):
    """Threaded comment on a prompt, optionally pinned to a specific version SHA."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt_id: str
    version_sha: str | None = None
    author: str
    body: str
    created_at: datetime = Field(default_factory=_utcnow)


class Collection(BaseModel):
    """Curated list of prompts grouped under a namespace."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Webhook(BaseModel):
    """HTTP endpoint registered to receive ``version.created`` (and other) events."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    events: list[str] = Field(default_factory=lambda: ["version.created"])
    secret: str
    namespace: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ServerIdentity(BaseModel):
    """This server's RSA identity (public key only; private key stored on disk)."""

    public_key_pem: str
    created_at: datetime


class Federation(BaseModel):
    """A named federation this server belongs to."""

    id: str
    name: str
    founding_key: str  # decrypted founding member's public key at read time
    is_founder: bool  # True if founding_key matches this server's public key
    created_at: datetime


class FederationMember(BaseModel):
    """A member record within a federation (decrypted at read time)."""

    id: str
    federation_id: str
    public_key: str  # decrypted public key PEM
    federate_url: str  # decrypted /v1/federate URL
    is_accepted: bool
    joined_at: datetime
    updated_at: datetime


class FederationPeer(BaseModel):
    """A remote Cantica instance registered as a read-only federation peer."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    # Outbound API key used when querying this peer; None for public instances.
    api_key: str | None = None
    added_at: datetime = Field(default_factory=_utcnow)
