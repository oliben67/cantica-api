# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import difflib
import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Third party imports:
import httpx
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Local imports:
from cantica.core.resolver import parse_address
from cantica.database import open_session
from cantica.models import (
    Branch,
    Collection,
    Comment,
    Fork,
    Namespace,
    Prompt,
    Star,
    Tag,
    VariableSchema,
    Version,
    Visibility,
    Webhook,
)
from cantica.orm.tables import (
    ApiKeyOrm,
    BranchOrm,
    CollectionItemOrm,
    CollectionOrm,
    CommentOrm,
    ForkOrm,
    NamespaceOrm,
    PromptOrm,
    StarOrm,
    TagOrm,
    VersionOrm,
    WebhookOrm,
)
from cantica.services.blob_store import BlobStore

_log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _commit_sha(
    content_sha: str,
    parent_sha: str | None,
    author: str,
    message: str,
    created_at: datetime,
) -> str:
    data = f"commit\n{content_sha}\n{parent_sha or ''}\n{author}\n{message}\n{_iso(created_at)}"
    return hashlib.sha256(data.encode()).hexdigest()


def _load_variables(raw: str) -> list[VariableSchema]:
    return [VariableSchema(**v) for v in json.loads(raw)]


def _orm_to_prompt(row: PromptOrm) -> Prompt:
    return Prompt(
        id=row.id,
        namespace=row.namespace,
        name=row.name,
        description=row.description,
        tags=json.loads(row.tags),
        model_hints=json.loads(row.model_hints),
        license=row.license,
        visibility=Visibility(row.visibility),
        variables=_load_variables(row.variables),
        star_count=row.star_count,
        fork_count=row.fork_count,
        default_branch=row.default_branch,
        created_at=_from_iso(row.created_at),
        updated_at=_from_iso(row.updated_at),
    )


class VersionStore:
    """Core service: prompts, commits, branches, tags, and ref resolution."""

    def __init__(
        self,
        root: Path,
        *,
        create_tables: bool = True,
        database_url: str | None = None,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = BlobStore(root / "objects")
        db: str | Path = database_url or (root / "cantica.db")
        self._engine, self.session = open_session(db, create_tables=create_tables)

    @property
    def _dialect(self) -> str:
        return self._engine.dialect.name

    def close(self) -> None:
        self.session.close()
        self._engine.dispose()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------ #
    # Namespaces                                                           #
    # ------------------------------------------------------------------ #

    def create_namespace(self, name: str, description: str = "") -> Namespace:
        ns = Namespace(name=name, description=description)
        self.session.execute(
            sqlite_insert(NamespaceOrm)
            .values(name=ns.name, description=ns.description, created_at=_iso(ns.created_at))
            .on_conflict_do_nothing(index_elements=["name"])
        )
        self.session.commit()
        return ns

    def get_namespace(self, name: str) -> Namespace | None:
        row = self.session.get(NamespaceOrm, name)
        if not row:
            return None
        return Namespace(
            name=row.name,
            description=row.description,
            created_at=_from_iso(row.created_at),
        )

    # ------------------------------------------------------------------ #
    # Prompts                                                              #
    # ------------------------------------------------------------------ #

    def create_prompt(
        self,
        namespace: str,
        name: str,
        description: str = "",
        *,
        tags: list[str] | None = None,
        model_hints: list[str] | None = None,
        license: str = "MIT",
        visibility: Visibility = Visibility.public,
        variables: list[VariableSchema] | None = None,
    ) -> Prompt:
        self.create_namespace(namespace)
        prompt = Prompt(
            namespace=namespace,
            name=name,
            description=description,
            tags=tags or [],
            model_hints=model_hints or [],
            license=license,
            visibility=visibility,
            variables=variables or [],
        )
        self.session.execute(
            sqlite_insert(PromptOrm).values(
                id=prompt.id,
                namespace=prompt.namespace,
                name=prompt.name,
                description=prompt.description,
                tags=json.dumps(prompt.tags),
                model_hints=json.dumps(prompt.model_hints),
                license=prompt.license,
                visibility=prompt.visibility.value,
                variables=json.dumps([v.model_dump() for v in prompt.variables]),
                star_count=prompt.star_count,
                fork_count=prompt.fork_count,
                default_branch=prompt.default_branch,
                created_at=_iso(prompt.created_at),
                updated_at=_iso(prompt.updated_at),
            )
        )
        if self._dialect == "sqlite":
            self.session.execute(
                text(
                    "INSERT INTO prompts_fts(prompt_id, name, description, body) "
                    "VALUES (:pid, :name, :desc, :body)"
                ),
                {
                    "pid": prompt.id,
                    "name": prompt.name,
                    "desc": prompt.description,
                    "body": " ".join(prompt.tags + prompt.model_hints),
                },
            )
        self.session.commit()
        return prompt

    def get_prompt(self, namespace: str, name: str) -> Prompt | None:
        row = self.session.execute(
            select(PromptOrm).where(PromptOrm.namespace == namespace, PromptOrm.name == name)
        ).scalar_one_or_none()
        return _orm_to_prompt(row) if row else None

    def list_prompts(
        self,
        namespace: str | None = None,
        *,
        tag: str | None = None,
        model: str | None = None,
        visibility: str | None = None,
    ) -> list[Prompt]:
        stmt = select(PromptOrm)
        if namespace is not None:
            stmt = stmt.where(PromptOrm.namespace == namespace)
        if tag is not None:
            stmt = stmt.where(PromptOrm.tags.contains(f'"{tag}"'))
        if model is not None:
            stmt = stmt.where(PromptOrm.model_hints.contains(f'"{model}"'))
        if visibility is not None:
            stmt = stmt.where(PromptOrm.visibility == visibility)
        rows = self.session.execute(stmt).scalars().all()
        return [_orm_to_prompt(r) for r in rows]

    def search_prompts(
        self,
        q: str,
        *,
        namespace: str | None = None,
        tag: str | None = None,
        model: str | None = None,
        visibility: str | None = None,
    ) -> list[Prompt]:
        """Full-text search over prompt name, description, tags, and model hints."""
        if self._dialect == "sqlite":
            fts_rows = self.session.execute(
                text("SELECT prompt_id FROM prompts_fts WHERE prompts_fts MATCH :q ORDER BY rank"),
                {"q": q},
            ).all()
        else:  # pragma: no cover
            fts_rows = self.session.execute(
                text(
                    "SELECT id AS prompt_id FROM prompts "
                    "WHERE search_vector @@ plainto_tsquery('english', :q) "
                    "ORDER BY ts_rank(search_vector, plainto_tsquery('english', :q)) DESC"
                ),
                {"q": q},
            ).all()
        if not fts_rows:
            return []
        ids = [r.prompt_id for r in fts_rows]
        id_rank = {pid: i for i, pid in enumerate(ids)}
        stmt = select(PromptOrm).where(PromptOrm.id.in_(ids))
        if namespace is not None:
            stmt = stmt.where(PromptOrm.namespace == namespace)
        if tag is not None:
            stmt = stmt.where(PromptOrm.tags.contains(f'"{tag}"'))
        if model is not None:
            stmt = stmt.where(PromptOrm.model_hints.contains(f'"{model}"'))
        if visibility is not None:
            stmt = stmt.where(PromptOrm.visibility == visibility)
        rows = self.session.execute(stmt).scalars().all()
        return sorted([_orm_to_prompt(r) for r in rows], key=lambda p: id_rank[p.id])

    def delete_prompt(self, prompt_id: str) -> None:
        if self._dialect == "sqlite":
            self.session.execute(
                text("DELETE FROM prompts_fts WHERE prompt_id = :pid"), {"pid": prompt_id}
            )
        self.session.execute(delete(TagOrm).where(TagOrm.prompt_id == prompt_id))
        self.session.execute(delete(BranchOrm).where(BranchOrm.prompt_id == prompt_id))
        self.session.execute(delete(VersionOrm).where(VersionOrm.prompt_id == prompt_id))
        self.session.execute(delete(PromptOrm).where(PromptOrm.id == prompt_id))
        self.session.commit()

    # ------------------------------------------------------------------ #
    # Commits                                                              #
    # ------------------------------------------------------------------ #

    def commit(
        self,
        prompt_id: str,
        content: str,
        message: str,
        author: str,
        branch: str = "main",
        variables: list[VariableSchema] | None = None,
    ) -> Version:
        content_sha = self.blobs.put(content)
        created_at = _utcnow()

        parent_branch = self.session.execute(
            select(BranchOrm).where(BranchOrm.prompt_id == prompt_id, BranchOrm.name == branch)
        ).scalar_one_or_none()
        parent_sha: str | None = parent_branch.head_sha if parent_branch else None

        sha = _commit_sha(content_sha, parent_sha, author, message, created_at)

        # Insert version first so BranchOrm FK (head_sha → versions.sha) is satisfied.
        self.session.execute(
            sqlite_insert(VersionOrm).values(
                sha=sha,
                prompt_id=prompt_id,
                branch=branch,
                parent_sha=parent_sha,
                message=message,
                author=author,
                content_sha=content_sha,
                variables=json.dumps([v.model_dump() for v in (variables or [])]),
                created_at=_iso(created_at),
            )
        )

        if parent_branch:
            self.session.execute(
                update(BranchOrm)
                .where(BranchOrm.prompt_id == prompt_id, BranchOrm.name == branch)
                .values(head_sha=sha, updated_at=_iso(created_at))
            )
        else:
            self.session.execute(
                sqlite_insert(BranchOrm).values(
                    name=branch,
                    prompt_id=prompt_id,
                    head_sha=sha,
                    created_at=_iso(created_at),
                    updated_at=_iso(created_at),
                )
            )

        self.session.execute(
            update(PromptOrm).where(PromptOrm.id == prompt_id).values(updated_at=_iso(created_at))
        )
        self.session.commit()

        version = Version(
            sha=sha,
            prompt_id=prompt_id,
            branch=branch,
            parent_sha=parent_sha,
            message=message,
            author=author,
            content=content,
            variables=variables or [],
            created_at=created_at,
        )

        prompt = self.session.get(PromptOrm, prompt_id)
        self.fire_webhooks(
            "version.created",
            {
                "event": "version.created",
                "sha": sha,
                "prompt_id": prompt_id,
                "namespace": prompt.namespace if prompt else "",
                "name": prompt.name if prompt else "",
                "branch": branch,
                "author": author,
                "message": message,
                "created_at": _iso(created_at),
            },
        )
        return version

    def has_version(self, sha: str) -> bool:
        return self.session.get(VersionOrm, sha) is not None

    def import_version(
        self,
        prompt_id: str,
        sha: str,
        content: str,
        message: str,
        author: str,
        branch: str,
        parent_sha: str | None,
        created_at: datetime,
        variables: list[VariableSchema] | None = None,
    ) -> Version:
        """Insert a version with a pre-computed SHA; used for push/pull sync."""
        content_sha = self.blobs.put(content)
        computed = _commit_sha(content_sha, parent_sha, author, message, created_at)
        if computed != sha:
            raise ValueError(f"SHA mismatch on import: expected {sha!r}, computed {computed!r}")
        if self.has_version(sha):
            return self.get_version(sha)  # type: ignore[return-value]

        self.session.execute(
            sqlite_insert(VersionOrm).values(
                sha=sha,
                prompt_id=prompt_id,
                branch=branch,
                parent_sha=parent_sha,
                message=message,
                author=author,
                content_sha=content_sha,
                variables=json.dumps([v.model_dump() for v in (variables or [])]),
                created_at=_iso(created_at),
            )
        )

        now = _utcnow()
        branch_row = self.session.execute(
            select(BranchOrm).where(BranchOrm.prompt_id == prompt_id, BranchOrm.name == branch)
        ).scalar_one_or_none()
        if branch_row:
            self.session.execute(
                update(BranchOrm)
                .where(BranchOrm.prompt_id == prompt_id, BranchOrm.name == branch)
                .values(head_sha=sha, updated_at=_iso(now))
            )
        else:
            self.session.execute(
                sqlite_insert(BranchOrm).values(
                    name=branch,
                    prompt_id=prompt_id,
                    head_sha=sha,
                    created_at=_iso(created_at),
                    updated_at=_iso(now),
                )
            )

        self.session.execute(
            update(PromptOrm).where(PromptOrm.id == prompt_id).values(updated_at=_iso(now))
        )
        self.session.commit()
        return self.get_version(sha)  # type: ignore[return-value]

    def get_version(self, sha: str) -> Version | None:
        row = self.session.get(VersionOrm, sha)
        if not row:
            return None
        content = self.blobs.get(row.content_sha)
        tag_rows = self.session.execute(
            select(TagOrm.name).where(TagOrm.prompt_id == row.prompt_id, TagOrm.sha == sha)
        ).all()
        return Version(
            sha=row.sha,
            prompt_id=row.prompt_id,
            branch=row.branch,
            parent_sha=row.parent_sha,
            message=row.message,
            author=row.author,
            content=content,
            variables=_load_variables(row.variables),
            created_at=_from_iso(row.created_at),
            tags=[r.name for r in tag_rows],
        )

    def log(self, prompt_id: str, branch: str = "main") -> list[Version]:
        rows = self.session.execute(
            select(VersionOrm.sha)
            .where(VersionOrm.prompt_id == prompt_id, VersionOrm.branch == branch)
            .order_by(VersionOrm.created_at.desc())
        ).all()
        return [v for r in rows if (v := self.get_version(r.sha)) is not None]

    # ------------------------------------------------------------------ #
    # Tags                                                                 #
    # ------------------------------------------------------------------ #

    def create_tag(self, prompt_id: str, tag_name: str, sha: str) -> Tag:
        created_at = _utcnow()
        ts = _iso(created_at)
        stmt = sqlite_insert(TagOrm).values(
            prompt_id=prompt_id, name=tag_name, sha=sha, created_at=ts
        )
        self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["prompt_id", "name"],
                set_={"sha": stmt.excluded.sha, "created_at": stmt.excluded.created_at},
            )
        )
        self.session.commit()
        return Tag(name=tag_name, prompt_id=prompt_id, sha=sha, created_at=created_at)

    def list_tags(self, prompt_id: str) -> list[Tag]:
        rows = (
            self.session.execute(
                select(TagOrm)
                .where(TagOrm.prompt_id == prompt_id)
                .order_by(TagOrm.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            Tag(
                name=r.name,
                prompt_id=r.prompt_id,
                sha=r.sha,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    def get_tag(self, prompt_id: str, tag_name: str) -> Tag | None:
        row = self.session.execute(
            select(TagOrm).where(TagOrm.prompt_id == prompt_id, TagOrm.name == tag_name)
        ).scalar_one_or_none()
        if not row:
            return None
        return Tag(
            name=row.name,
            prompt_id=row.prompt_id,
            sha=row.sha,
            created_at=_from_iso(row.created_at),
        )

    # ------------------------------------------------------------------ #
    # Branches                                                             #
    # ------------------------------------------------------------------ #

    def create_branch(self, prompt_id: str, branch_name: str, from_sha: str) -> Branch:
        created_at = _utcnow()
        ts = _iso(created_at)
        stmt = sqlite_insert(BranchOrm).values(
            name=branch_name, prompt_id=prompt_id, head_sha=from_sha, created_at=ts, updated_at=ts
        )
        self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["prompt_id", "name"],
                set_={
                    "head_sha": stmt.excluded.head_sha,
                    "created_at": stmt.excluded.created_at,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
        )
        self.session.commit()
        return Branch(
            name=branch_name,
            prompt_id=prompt_id,
            head_sha=from_sha,
            created_at=created_at,
            updated_at=created_at,
        )

    def get_branch(self, prompt_id: str, branch_name: str) -> Branch | None:
        row = self.session.execute(
            select(BranchOrm).where(BranchOrm.prompt_id == prompt_id, BranchOrm.name == branch_name)
        ).scalar_one_or_none()
        if not row:
            return None
        return Branch(
            name=row.name,
            prompt_id=row.prompt_id,
            head_sha=row.head_sha,
            created_at=_from_iso(row.created_at),
            updated_at=_from_iso(row.updated_at),
        )

    def list_branches(self, prompt_id: str) -> list[Branch]:
        rows = (
            self.session.execute(select(BranchOrm).where(BranchOrm.prompt_id == prompt_id))
            .scalars()
            .all()
        )
        return [
            Branch(
                name=r.name,
                prompt_id=r.prompt_id,
                head_sha=r.head_sha,
                created_at=_from_iso(r.created_at),
                updated_at=_from_iso(r.updated_at),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Diff                                                                 #
    # ------------------------------------------------------------------ #

    def diff(self, sha1: str, sha2: str) -> str:
        v1 = self.get_version(sha1)
        v2 = self.get_version(sha2)
        if not v1:
            raise KeyError(f"version {sha1!r} not found")
        if not v2:
            raise KeyError(f"version {sha2!r} not found")
        lines1 = v1.content.splitlines(keepends=True)
        lines2 = v2.content.splitlines(keepends=True)
        return "".join(difflib.unified_diff(lines1, lines2, fromfile=sha1[:7], tofile=sha2[:7]))

    # ------------------------------------------------------------------ #
    # Ref resolution                                                       #
    # ------------------------------------------------------------------ #

    def resolve(self, namespace: str, name: str, ref: str = "latest") -> Version:
        """Resolve namespace/name@ref to a concrete Version."""
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"prompt {namespace}/{name} not found")

        # "latest" or default branch name → head of default branch
        if ref in ("latest", prompt.default_branch):
            branch = self.get_branch(prompt.id, prompt.default_branch)
            if not branch:
                raise KeyError(f"{namespace}/{name} has no commits")
            version = self.get_version(branch.head_sha)
            if not version:
                raise KeyError(f"dangling branch head {branch.head_sha!r}")
            return version

        # named tag
        tag = self.get_tag(prompt.id, ref)
        if tag:
            version = self.get_version(tag.sha)
            if version:  # pragma: no branch
                return version

        # named branch
        branch_obj = self.get_branch(prompt.id, ref)
        if branch_obj:
            version = self.get_version(branch_obj.head_sha)
            if version:  # pragma: no branch
                return version

        # exact SHA
        version = self.get_version(ref)
        if version and version.prompt_id == prompt.id:
            return version

        # SHA prefix
        rows = self.session.execute(
            select(VersionOrm.sha).where(
                VersionOrm.prompt_id == prompt.id, VersionOrm.sha.like(ref + "%")
            )
        ).all()
        if len(rows) == 1:
            version = self.get_version(rows[0].sha)
            if version:  # pragma: no branch
                return version
        if len(rows) > 1:
            raise ValueError(f"ambiguous ref {ref!r} — matches {len(rows)} versions")

        raise KeyError(f"ref {ref!r} not found in {namespace}/{name}")

    # ------------------------------------------------------------------ #
    # Fork                                                                 #
    # ------------------------------------------------------------------ #

    def fork(
        self,
        source_namespace: str,
        source_name: str,
        dest_namespace: str,
        dest_name: str,
        branch: str = "main",
    ) -> Fork:
        """Copy all versions from source into a new prompt, recording lineage."""
        source = self.get_prompt(source_namespace, source_name)
        if not source:
            raise KeyError(f"prompt {source_namespace}/{source_name} not found")
        if self.get_prompt(dest_namespace, dest_name):
            raise ValueError(f"prompt {dest_namespace}/{dest_name} already exists")

        source_branch = self.get_branch(source.id, branch)
        source_sha = source_branch.head_sha if source_branch else ""

        dest = self.create_prompt(
            dest_namespace,
            dest_name,
            description=source.description,
            tags=source.tags,
            model_hints=source.model_hints,
            license=source.license,
            visibility=source.visibility,
            variables=source.variables,
        )

        # re-commit all versions oldest-first under the new prompt_id
        sha_map: dict[str, str] = {}
        for v in reversed(self.log(source.id, branch)):
            new_v = self.commit(dest.id, v.content, v.message, v.author, branch, v.variables)
            sha_map[v.sha] = new_v.sha

        # copy tags, remapping to new SHAs
        for t in self.list_tags(source.id):
            if t.sha in sha_map:
                self.create_tag(dest.id, t.name, sha_map[t.sha])

        # increment source fork_count
        self.session.execute(
            update(PromptOrm)
            .where(PromptOrm.id == source.id)
            .values(fork_count=PromptOrm.fork_count + 1)
        )

        fork_record = Fork(
            source_slug=source.slug,
            source_sha=source_sha,
            fork_slug=dest.slug,
        )
        self.session.execute(
            sqlite_insert(ForkOrm).values(
                id=fork_record.id,
                source_slug=fork_record.source_slug,
                source_sha=fork_record.source_sha,
                fork_slug=fork_record.fork_slug,
                created_at=_iso(fork_record.created_at),
            )
        )
        self.session.commit()
        return fork_record

    def list_forks(self, namespace: str, name: str) -> list[Fork]:
        slug = f"{namespace}/{name}"
        rows = (
            self.session.execute(
                select(ForkOrm)
                .where(ForkOrm.source_slug == slug)
                .order_by(ForkOrm.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            Fork(
                id=r.id,
                source_slug=r.source_slug,
                source_sha=r.source_sha,
                fork_slug=r.fork_slug,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Rollback                                                             #
    # ------------------------------------------------------------------ #

    def rollback(self, namespace: str, name: str, ref: str, branch: str = "main") -> Version:
        """Reset a branch head to a past ref. Returns the version now at head."""
        version = self.resolve(namespace, name, ref)
        prompt = self.get_prompt(namespace, name)
        if not prompt:  # pragma: no cover  — resolve() already raises
            raise KeyError(f"prompt {namespace}/{name} not found")
        self.session.execute(
            update(BranchOrm)
            .where(BranchOrm.prompt_id == prompt.id, BranchOrm.name == branch)
            .values(head_sha=version.sha, updated_at=_iso(_utcnow()))
        )
        self.session.commit()
        return version

    # ------------------------------------------------------------------ #
    # Merge (fast-forward only)                                            #
    # ------------------------------------------------------------------ #

    def merge(
        self, namespace: str, name: str, from_branch: str, into_branch: str = "main"
    ) -> Version:
        """Fast-forward merge from_branch into into_branch.

        Walks the parent chain of from_branch head; if into_branch head is an
        ancestor (or into_branch has no commits), advances into_branch head.
        Raises ValueError when a fast-forward is not possible.
        """
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"prompt {namespace}/{name} not found")

        src_branch = self.get_branch(prompt.id, from_branch)
        if not src_branch:
            raise KeyError(f"branch {from_branch!r} not found in {namespace}/{name}")

        dst_branch = self.get_branch(prompt.id, into_branch)

        # if destination has no commits, just point it at source head
        if not dst_branch:
            self.create_branch(prompt.id, into_branch, src_branch.head_sha)
            return self.get_version(src_branch.head_sha)  # type: ignore[return-value]

        # already up to date
        if dst_branch.head_sha == src_branch.head_sha:
            return self.get_version(src_branch.head_sha)  # type: ignore[return-value]

        # walk parent chain of src to see if dst head is an ancestor
        sha: str | None = src_branch.head_sha
        while sha:
            if sha == dst_branch.head_sha:
                break
            sha = self.session.execute(
                select(VersionOrm.parent_sha).where(VersionOrm.sha == sha)
            ).scalar_one_or_none()
        else:
            raise ValueError(
                f"cannot fast-forward {into_branch!r} to {from_branch!r}: histories have diverged"
            )

        self.session.execute(
            update(BranchOrm)
            .where(BranchOrm.prompt_id == prompt.id, BranchOrm.name == into_branch)
            .values(head_sha=src_branch.head_sha, updated_at=_iso(_utcnow()))
        )
        self.session.commit()
        return self.get_version(src_branch.head_sha)  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # API keys                                                             #
    # ------------------------------------------------------------------ #

    def create_api_key(self, name: str, key_hash: str) -> tuple[str, datetime]:
        token_id = str(uuid.uuid4())
        created_at = _utcnow()
        self.session.add(
            ApiKeyOrm(id=token_id, name=name, key_hash=key_hash, created_at=_iso(created_at))
        )
        self.session.commit()
        return token_id, created_at

    def list_api_keys(self) -> list[tuple[str, str, datetime, datetime | None]]:
        rows = (
            self.session.execute(select(ApiKeyOrm).order_by(ApiKeyOrm.created_at.desc()))
            .scalars()
            .all()
        )
        return [
            (
                r.id,
                r.name,
                _from_iso(r.created_at),
                _from_iso(r.last_used_at) if r.last_used_at else None,
            )
            for r in rows
        ]

    def revoke_api_key(self, token_id: str) -> bool:
        result = self.session.execute(delete(ApiKeyOrm).where(ApiKeyOrm.id == token_id))
        self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    def verify_api_key(self, key_hash: str) -> dict[str, str] | None:
        row = self.session.execute(
            select(ApiKeyOrm).where(ApiKeyOrm.key_hash == key_hash)
        ).scalar_one_or_none()
        if not row:
            return None
        self.session.execute(
            update(ApiKeyOrm).where(ApiKeyOrm.id == row.id).values(last_used_at=_iso(_utcnow()))
        )
        self.session.commit()
        return {"id": row.id, "name": row.name}

    # ------------------------------------------------------------------ #
    # cantica:// URI resolution                                            #
    # ------------------------------------------------------------------ #

    def resolve_uri(self, uri: str, remote_url: str | None = None) -> Version:
        """Resolve a cantica:// URI to a Version.

        If the address has a host, fetch the version from that remote
        instance (or from `remote_url` if provided). Otherwise resolve
        against the local vault.
        """
        addr = parse_address(uri)
        if addr.host is None:
            return self.resolve(addr.namespace, addr.name, addr.ref)

        base = (remote_url or f"https://{addr.host}").rstrip("/")
        url = f"{base}/v1/prompts/{addr.namespace}/{addr.name}/versions/{addr.ref}"
        try:
            resp = httpx.get(url, timeout=10)
        except httpx.RequestError as exc:
            raise ConnectionError(f"could not reach {base}: {exc}") from exc
        if resp.status_code == 404:
            raise KeyError(f"{addr.namespace}/{addr.name}@{addr.ref} not found on {base}")
        resp.raise_for_status()
        data = resp.json()
        return Version(
            sha=data["sha"],
            prompt_id=data["prompt_id"],
            branch=data.get("branch", "main"),
            parent_sha=data.get("parent_sha"),
            message=data["message"],
            author=data["author"],
            content=data["content"],
            variables=[VariableSchema(**v) for v in data.get("variables", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=data.get("tags", []),
        )

    # ------------------------------------------------------------------ #
    # Stars                                                                #
    # ------------------------------------------------------------------ #

    def star_prompt(self, namespace: str, name: str, actor: str) -> Star:
        self.create_namespace(actor)
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"{namespace}/{name}")
        existing = self.session.execute(
            select(StarOrm).where(StarOrm.namespace == actor, StarOrm.prompt_id == prompt.id)
        ).scalar_one_or_none()
        if existing:
            return Star(
                id=existing.id,
                namespace=existing.namespace,
                prompt_id=existing.prompt_id,
                created_at=_from_iso(existing.created_at),
            )
        now = _utcnow()
        row = StarOrm(
            id=str(uuid.uuid4()), namespace=actor, prompt_id=prompt.id, created_at=_iso(now)
        )
        self.session.add(row)
        self.session.execute(
            update(PromptOrm)
            .where(PromptOrm.id == prompt.id)
            .values(star_count=PromptOrm.star_count + 1)
        )
        self.session.commit()
        return Star(id=row.id, namespace=actor, prompt_id=prompt.id, created_at=now)

    def unstar_prompt(self, namespace: str, name: str, actor: str) -> bool:
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"{namespace}/{name}")
        result = self.session.execute(
            delete(StarOrm).where(StarOrm.namespace == actor, StarOrm.prompt_id == prompt.id)
        )
        if result.rowcount > 0:  # type: ignore[attr-defined]
            self.session.execute(
                update(PromptOrm)
                .where(PromptOrm.id == prompt.id)
                .values(star_count=PromptOrm.star_count - 1)
            )
        self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    def list_stargazers(self, namespace: str, name: str) -> list[Star]:
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"{namespace}/{name}")
        rows = (
            self.session.execute(select(StarOrm).where(StarOrm.prompt_id == prompt.id))
            .scalars()
            .all()
        )
        return [
            Star(
                id=r.id,
                namespace=r.namespace,
                prompt_id=r.prompt_id,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Comments                                                             #
    # ------------------------------------------------------------------ #

    def add_comment(
        self, namespace: str, name: str, body: str, author: str, version_sha: str | None = None
    ) -> Comment:
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"{namespace}/{name}")
        now = _utcnow()
        row = CommentOrm(
            id=str(uuid.uuid4()),
            prompt_id=prompt.id,
            version_sha=version_sha,
            author=author,
            body=body,
            created_at=_iso(now),
        )
        self.session.add(row)
        self.session.commit()
        return Comment(
            id=row.id,
            prompt_id=prompt.id,
            version_sha=version_sha,
            author=author,
            body=body,
            created_at=now,
        )

    def list_comments(
        self, namespace: str, name: str, version_sha: str | None = None
    ) -> list[Comment]:
        prompt = self.get_prompt(namespace, name)
        if not prompt:
            raise KeyError(f"{namespace}/{name}")
        stmt = select(CommentOrm).where(CommentOrm.prompt_id == prompt.id)
        if version_sha is not None:
            stmt = stmt.where(CommentOrm.version_sha == version_sha)
        stmt = stmt.order_by(CommentOrm.created_at)
        rows = self.session.execute(stmt).scalars().all()
        return [
            Comment(
                id=r.id,
                prompt_id=r.prompt_id,
                version_sha=r.version_sha,
                author=r.author,
                body=r.body,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    def delete_comment(self, comment_id: str) -> bool:
        result = self.session.execute(delete(CommentOrm).where(CommentOrm.id == comment_id))
        self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # Collections                                                          #
    # ------------------------------------------------------------------ #

    def create_collection(self, namespace: str, name: str, description: str = "") -> Collection:
        self.create_namespace(namespace)
        existing = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Collection {namespace}/{name} already exists")
        now = _utcnow()
        row = CollectionOrm(
            id=str(uuid.uuid4()),
            namespace=namespace,
            name=name,
            description=description,
            created_at=_iso(now),
        )
        self.session.add(row)
        self.session.commit()
        return Collection(
            id=row.id, namespace=namespace, name=name, description=description, created_at=now
        )

    def get_collection(self, namespace: str, name: str) -> Collection | None:
        row = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if not row:
            return None
        return Collection(
            id=row.id,
            namespace=row.namespace,
            name=row.name,
            description=row.description,
            created_at=_from_iso(row.created_at),
        )

    def list_collections(self, namespace: str | None = None) -> list[Collection]:
        stmt = select(CollectionOrm)
        if namespace is not None:
            stmt = stmt.where(CollectionOrm.namespace == namespace)
        rows = self.session.execute(stmt).scalars().all()
        return [
            Collection(
                id=r.id,
                namespace=r.namespace,
                name=r.name,
                description=r.description,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    def delete_collection(self, namespace: str, name: str) -> bool:
        row = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if not row:
            return False
        self.session.execute(
            delete(CollectionItemOrm).where(CollectionItemOrm.collection_id == row.id)
        )
        self.session.execute(delete(CollectionOrm).where(CollectionOrm.id == row.id))
        self.session.commit()
        return True

    def add_to_collection(self, namespace: str, name: str, prompt_slug: str) -> None:
        coll = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if not coll:
            raise KeyError(f"Collection {namespace}/{name} not found")
        ns, pname = prompt_slug.split("/", 1)
        prompt = self.get_prompt(ns, pname)
        if not prompt:
            raise KeyError(f"Prompt {prompt_slug} not found")
        existing = self.session.execute(
            select(CollectionItemOrm).where(
                CollectionItemOrm.collection_id == coll.id,
                CollectionItemOrm.prompt_id == prompt.id,
            )
        ).scalar_one_or_none()
        if not existing:
            self.session.add(
                CollectionItemOrm(
                    collection_id=coll.id, prompt_id=prompt.id, added_at=_iso(_utcnow())
                )
            )
            self.session.commit()

    def remove_from_collection(self, namespace: str, name: str, prompt_slug: str) -> bool:
        coll = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if not coll:
            raise KeyError(f"Collection {namespace}/{name} not found")
        ns, pname = prompt_slug.split("/", 1)
        prompt = self.get_prompt(ns, pname)
        if not prompt:
            return False
        result = self.session.execute(
            delete(CollectionItemOrm).where(
                CollectionItemOrm.collection_id == coll.id,
                CollectionItemOrm.prompt_id == prompt.id,
            )
        )
        self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    def list_collection_items(self, namespace: str, name: str) -> list[Prompt]:
        coll = self.session.execute(
            select(CollectionOrm).where(
                CollectionOrm.namespace == namespace, CollectionOrm.name == name
            )
        ).scalar_one_or_none()
        if not coll:
            raise KeyError(f"Collection {namespace}/{name} not found")
        rows = (
            self.session.execute(
                select(PromptOrm)
                .join(CollectionItemOrm, CollectionItemOrm.prompt_id == PromptOrm.id)
                .where(CollectionItemOrm.collection_id == coll.id)
                .order_by(CollectionItemOrm.added_at)
            )
            .scalars()
            .all()
        )
        return [_orm_to_prompt(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Webhooks                                                             #
    # ------------------------------------------------------------------ #

    def create_webhook(
        self,
        url: str,
        secret: str,
        events: list[str] | None = None,
        namespace: str | None = None,
    ) -> Webhook:
        now = _utcnow()
        hook = Webhook(
            url=url,
            secret=secret,
            events=events or ["version.created"],
            namespace=namespace,
        )
        self.session.add(
            WebhookOrm(
                id=hook.id,
                url=hook.url,
                events=json.dumps(hook.events),
                secret=hook.secret,
                namespace=hook.namespace,
                created_at=_iso(now),
            )
        )
        self.session.commit()
        return hook

    def list_webhooks(self) -> list[Webhook]:
        rows = (
            self.session.execute(select(WebhookOrm).order_by(WebhookOrm.created_at)).scalars().all()
        )
        return [
            Webhook(
                id=r.id,
                url=r.url,
                events=json.loads(r.events),
                secret=r.secret,
                namespace=r.namespace,
                created_at=_from_iso(r.created_at),
            )
            for r in rows
        ]

    def delete_webhook(self, webhook_id: str) -> bool:
        result = self.session.execute(delete(WebhookOrm).where(WebhookOrm.id == webhook_id))
        self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    def fire_webhooks(self, event: str, payload: dict) -> None:
        """POST event payload to all matching registered webhooks (best-effort)."""
        rows = self.session.execute(select(WebhookOrm)).scalars().all()
        if not rows:
            return
        body = json.dumps(payload).encode()
        for row in rows:
            if event not in json.loads(row.events):
                continue
            if row.namespace and payload.get("namespace") != row.namespace:
                continue
            sig = "sha256=" + hmac.new(row.secret.encode(), body, hashlib.sha256).hexdigest()
            try:
                httpx.post(
                    row.url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Cantica-Event": event,
                        "X-Cantica-Signature": sig,
                    },
                    timeout=5,
                )
            except Exception:
                _log.warning("webhook delivery failed for %s → %s", event, row.url)
