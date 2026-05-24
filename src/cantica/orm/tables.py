"""
SQLAlchemy ORM table definitions for every entity in the Cantica schema.

All datetime and JSON-array columns are stored as plain ``String`` / VARCHAR
values (ISO-8601 strings for timestamps; ``json.dumps`` / ``json.loads`` for
lists).  This avoids dialect-specific type quirks and keeps the schema
portable between SQLite and PostgreSQL.

Tables
------
NamespaceOrm
    One row per user/organisation namespace.  Primary key: ``name``.

PromptOrm
    Core prompt metadata.  Unique on ``(namespace, name)``.  The ``tags``,
    ``model_hints``, and ``variables`` columns store JSON arrays as strings.
    ``star_count`` and ``fork_count`` are denormalised counters updated in-place.

VersionOrm
    Immutable commit records.  Primary key: ``sha`` (git-style commit hash).
    ``content_sha`` is the SHA-256 of the raw content and acts as the foreign
    key into the ``BlobStore``.  Self-referential ``parent_sha`` FK captures
    the linear commit chain.  Composite indexes on ``(prompt_id, branch)`` and
    ``(prompt_id, created_at)`` speed up log and branch-head lookups.

TagOrm
    Named refs pointing to a ``sha``.  Composite PK: ``(prompt_id, name)``.
    Upsert semantics (``on_conflict_do_update``) allow re-tagging.

BranchOrm
    Mutable branch heads.  Composite PK: ``(prompt_id, name)``.
    ``head_sha`` FK → ``versions.sha`` is updated on every ``commit()``.

ForkOrm
    Lineage audit log: ``source_slug → fork_slug`` with the SHA at fork time.

StarOrm
    Many-to-many between namespaces and prompts.  Unique on
    ``(namespace, prompt_id)`` so a namespace can star a prompt at most once.

CommentOrm
    Threaded comments.  ``version_sha`` is nullable — ``NULL`` means a comment
    on the prompt as a whole rather than a specific version.

CollectionOrm / CollectionItemOrm
    Curated lists of prompts.  ``collection_items`` is a join table with
    ``added_at`` for ordering.

WebhookOrm
    HTTP webhook registrations.  ``events`` is a JSON array of event names
    (e.g. ``["version.created"]``).  Optional ``namespace`` filter limits
    deliveries to events from a specific namespace.

ApiKeyOrm
    Hashed API tokens for authentication.  The raw key is shown to the user
    once and never stored; only the ``key_hash`` (SHA-256) is persisted.
    ``last_used_at`` is updated on every successful verification.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

# Local imports:
from cantica.orm.base import Base


class NamespaceOrm(Base):
    """SQLAlchemy ORM table: ``namespaces``."""

    __tablename__ = "namespaces"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, default="")
    is_proprietary: Mapped[bool] = mapped_column(Integer, default=0)
    encoded: Mapped[bool] = mapped_column(Integer, default=0)
    # AES-256 key (hex-encoded, 64 chars). Only set when encoded=True.
    encryption_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class PromptOrm(Base):
    """SQLAlchemy ORM table: ``prompts``.  Tags, model_hints, and variables are stored as JSON."""

    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("namespace", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[str] = mapped_column(String, default="[]")
    model_hints: Mapped[str] = mapped_column(String, default="[]")
    license: Mapped[str] = mapped_column(String, default="MIT")
    visibility: Mapped[str] = mapped_column(String, default="public")
    variables: Mapped[str] = mapped_column(String, default="[]")
    star_count: Mapped[int] = mapped_column(Integer, default=0)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)
    default_branch: Mapped[str] = mapped_column(String, default="main")
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class VersionOrm(Base):
    """SQLAlchemy ORM table: ``versions``.  Content is stored in the BlobStore; only the SHA here."""

    __tablename__ = "versions"
    __table_args__ = (
        Index("idx_versions_prompt_branch", "prompt_id", "branch"),
        Index("idx_versions_prompt_created", "prompt_id", "created_at"),
    )

    sha: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"))
    branch: Mapped[str] = mapped_column(String, default="main")
    parent_sha: Mapped[str | None] = mapped_column(
        String, ForeignKey("versions.sha"), nullable=True
    )
    message: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String)
    content_sha: Mapped[str] = mapped_column(String)
    is_encoded: Mapped[bool] = mapped_column(Integer, default=0)
    variables: Mapped[str] = mapped_column(String, default="[]")
    created_at: Mapped[str] = mapped_column(String)


class TagOrm(Base):
    """SQLAlchemy ORM table: ``tags``.  Named pointer to a version SHA."""

    __tablename__ = "tags"

    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String, primary_key=True)
    sha: Mapped[str] = mapped_column(String, ForeignKey("versions.sha"))
    created_at: Mapped[str] = mapped_column(String)


class BranchOrm(Base):
    """SQLAlchemy ORM table: ``branches``.  Mutable pointer to the branch head SHA."""

    __tablename__ = "branches"

    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String, primary_key=True)
    head_sha: Mapped[str] = mapped_column(String, ForeignKey("versions.sha"))
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class ForkOrm(Base):
    """SQLAlchemy ORM table: ``forks``.  Lineage record linking source slug to fork slug."""

    __tablename__ = "forks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_slug: Mapped[str] = mapped_column(String)
    source_sha: Mapped[str] = mapped_column(String)
    fork_slug: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class StarOrm(Base):
    """SQLAlchemy ORM table: ``stars``.  Records a namespace starring a prompt."""

    __tablename__ = "stars"
    __table_args__ = (UniqueConstraint("namespace", "prompt_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"))
    created_at: Mapped[str] = mapped_column(String)


class CommentOrm(Base):
    """SQLAlchemy ORM table: ``comments``.  Threaded comment on a prompt or version."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"))
    version_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class CollectionOrm(Base):
    """SQLAlchemy ORM table: ``collections``.  Curated list of prompts under a namespace."""

    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("namespace", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class CollectionItemOrm(Base):
    """SQLAlchemy ORM table: ``collection_items``.  Join table linking collections to prompts."""

    __tablename__ = "collection_items"

    collection_id: Mapped[str] = mapped_column(
        String, ForeignKey("collections.id"), primary_key=True
    )
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    added_at: Mapped[str] = mapped_column(String)


class WebhookOrm(Base):
    """SQLAlchemy ORM table: ``webhooks``.  Registered HTTP endpoints for event delivery."""

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String)
    events: Mapped[str] = mapped_column(String, default='["version.created"]')
    secret: Mapped[str] = mapped_column(String)
    namespace: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class ApiKeyOrm(Base):
    """SQLAlchemy ORM table: ``api_keys``.  Stores hashed API keys (raw key never persisted)."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    key_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[str] = mapped_column(String)
    last_used_at: Mapped[str | None] = mapped_column(String, nullable=True)


class NamespaceCertOrm(Base):
    """Issued namespace access certificates (metadata only; raw token not stored)."""

    __tablename__ = "namespace_certs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    granted_to: Mapped[str] = mapped_column(String)
    issued_at: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    revoked: Mapped[bool] = mapped_column(Integer, default=0)


class InstanceConfigOrm(Base):
    """Single-row table holding instance-wide configuration (signing secret, etc.)."""

    __tablename__ = "instance_config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
