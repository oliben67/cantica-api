# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

# Local imports:
from cantica.orm.base import Base


class NamespaceOrm(Base):
    __tablename__ = "namespaces"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class PromptOrm(Base):
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
    variables: Mapped[str] = mapped_column(String, default="[]")
    created_at: Mapped[str] = mapped_column(String)


class TagOrm(Base):
    __tablename__ = "tags"

    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String, primary_key=True)
    sha: Mapped[str] = mapped_column(String, ForeignKey("versions.sha"))
    created_at: Mapped[str] = mapped_column(String)


class BranchOrm(Base):
    __tablename__ = "branches"

    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String, primary_key=True)
    head_sha: Mapped[str] = mapped_column(String, ForeignKey("versions.sha"))
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class ForkOrm(Base):
    __tablename__ = "forks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_slug: Mapped[str] = mapped_column(String)
    source_sha: Mapped[str] = mapped_column(String)
    fork_slug: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class StarOrm(Base):
    __tablename__ = "stars"
    __table_args__ = (UniqueConstraint("namespace", "prompt_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"))
    created_at: Mapped[str] = mapped_column(String)


class CommentOrm(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"))
    version_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class CollectionOrm(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("namespace", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    namespace: Mapped[str] = mapped_column(String, ForeignKey("namespaces.name"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String)


class CollectionItemOrm(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[str] = mapped_column(
        String, ForeignKey("collections.id"), primary_key=True
    )
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompts.id"), primary_key=True)
    added_at: Mapped[str] = mapped_column(String)


class WebhookOrm(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String)
    events: Mapped[str] = mapped_column(String, default='["version.created"]')
    secret: Mapped[str] = mapped_column(String)
    namespace: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class ApiKeyOrm(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    key_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[str] = mapped_column(String)
    last_used_at: Mapped[str | None] = mapped_column(String, nullable=True)
