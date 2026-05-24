# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import asyncio
import builtins
import json
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Third party imports:
from fastapi import FastAPI

# Local imports:
from cantica.api.v1.router import router as _api_router
from cantica.config import Settings
from cantica.core.security import generate_api_key
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
from cantica.services.template_engine import TemplateEngine
from cantica.services.version_store import VersionStore

# ---------------------------------------------------------------------------
# Sync helper (always called inside asyncio.to_thread — never on the event loop)
# ---------------------------------------------------------------------------


def _require_prompt_id(store: VersionStore, namespace: str, name: str) -> str:
    """Resolve *namespace/name* to a prompt ID, raising ``KeyError`` if absent."""
    prompt = store.get_prompt(namespace, name)
    if prompt is None:
        raise KeyError(f"{namespace}/{name}")
    return prompt.id


# ---------------------------------------------------------------------------
# Auth result types (avoid exposing raw tuples to callers)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TokenResult:
    """Returned by ``_Auth.create_token`` — includes the raw key (shown once)."""

    id: str
    name: str
    key: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TokenInfo:
    """Returned by ``_Auth.list_tokens`` — does not include the raw key."""

    id: str
    name: str
    created_at: datetime
    last_used_at: datetime | None


# ---------------------------------------------------------------------------
# Async namespace groups
# ---------------------------------------------------------------------------


class _Namespaces:
    """Async façade for namespace operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(self, name: str, description: str = "") -> Namespace:
        """Create and return a new namespace named *name*."""
        return await asyncio.to_thread(self._s.create_namespace, name, description)

    async def get(self, name: str) -> Namespace | None:
        """Return the namespace *name*, or ``None`` if it does not exist."""
        return await asyncio.to_thread(self._s.get_namespace, name)


class _Prompts:
    """Async façade for prompt CRUD operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(
        self,
        namespace: str,
        name: str,
        description: str = "",
        *,
        tags: builtins.list[str] | None = None,
        model_hints: builtins.list[str] | None = None,
        license: str = "MIT",
        visibility: str | Visibility = Visibility.public,
        variables: builtins.list[VariableSchema] | None = None,
    ) -> Prompt:
        """Create a new prompt *namespace/name* and return it."""
        _vis = Visibility(visibility) if isinstance(visibility, str) else visibility

        def _sync() -> Prompt:
            return self._s.create_prompt(
                namespace,
                name,
                description,
                tags=tags,
                model_hints=model_hints,
                license=license,
                visibility=_vis,
                variables=variables,
            )

        return await asyncio.to_thread(_sync)

    async def get(self, namespace: str, name: str) -> Prompt | None:
        """Return the prompt *namespace/name*, or ``None`` if absent."""
        return await asyncio.to_thread(self._s.get_prompt, namespace, name)

    async def list(
        self,
        namespace: str | None = None,
        *,
        tag: str | None = None,
        model: str | None = None,
        visibility: str | None = None,
    ) -> builtins.list[Prompt]:
        """List prompts, optionally filtered by namespace, tag, model, or visibility."""
        return await asyncio.to_thread(
            self._s.list_prompts, namespace, tag=tag, model=model, visibility=visibility
        )

    async def search(
        self,
        q: str,
        *,
        namespace: str | None = None,
        tag: str | None = None,
        model: str | None = None,
        visibility: str | None = None,
    ) -> builtins.list[Prompt]:
        """Full-text search prompts matching *q*."""
        return await asyncio.to_thread(
            self._s.search_prompts,
            q,
            namespace=namespace,
            tag=tag,
            model=model,
            visibility=visibility,
        )

    async def delete(self, namespace: str, name: str) -> None:
        """Permanently delete the prompt *namespace/name* and all its versions."""

        """Permanently delete the prompt *namespace/name* and all its versions."""

        def _sync() -> None:
            self._s.delete_prompt(_require_prompt_id(self._s, namespace, name))

        await asyncio.to_thread(_sync)


class _Versions:
    """Async façade for version/commit operations on the local store."""

    __slots__ = ("_s", "_engine")

    def __init__(self, store: VersionStore, engine: TemplateEngine) -> None:
        """Bind to *store* and *engine*."""
        self._s = store
        self._engine = engine

    async def commit(
        self,
        namespace: str,
        name: str,
        content: str,
        message: str,
        author: str,
        branch: str = "main",
        variables: builtins.list[VariableSchema] | None = None,
    ) -> Version:
        """Commit *content* to *namespace/name* on *branch* and return the new version."""
        def _sync() -> Version:
            return self._s.commit(
                _require_prompt_id(self._s, namespace, name),
                content,
                message,
                author,
                branch,
                variables=variables,
            )

        return await asyncio.to_thread(_sync)

    async def get(self, sha: str) -> Version | None:
        """Fetch the version identified by *sha*, or ``None`` if not found."""
        return await asyncio.to_thread(self._s.get_version, sha)

    async def has_version(self, sha: str) -> bool:
        """Return ``True`` if the store already contains *sha*."""
        return await asyncio.to_thread(self._s.has_version, sha)

    async def log(self, namespace: str, name: str, branch: str = "main") -> builtins.list[Version]:
        """Return the commit history of *namespace/name* on *branch*, newest first."""

        def _sync() -> builtins.list[Version]:
            return self._s.log(_require_prompt_id(self._s, namespace, name), branch)

        return await asyncio.to_thread(_sync)

    async def import_version(
        self,
        namespace: str,
        name: str,
        sha: str,
        content: str,
        message: str,
        author: str,
        branch: str,
        parent_sha: str | None,
        created_at: datetime,
        variables: builtins.list[VariableSchema] | None = None,
    ) -> Version:
        """Import a version with a pre-computed *sha* (used during push/ingest)."""
        def _sync() -> Version:
            return self._s.import_version(
                _require_prompt_id(self._s, namespace, name),
                sha,
                content,
                message,
                author,
                branch,
                parent_sha,
                created_at,
                variables=variables,
            )

        return await asyncio.to_thread(_sync)

    async def resolve(self, namespace: str, name: str, ref: str = "latest") -> Version:
        """Resolve *ref* (SHA, branch, tag, or ``latest``) for *namespace/name*."""
        return await asyncio.to_thread(self._s.resolve, namespace, name, ref)

    async def resolve_uri(self, uri: str, remote_url: str | None = None) -> Version:
        """Resolve a ``cantica://`` URI, fetching remotely if *remote_url* is given."""
        return await asyncio.to_thread(self._s.resolve_uri, uri, remote_url)

    async def render(
        self,
        namespace: str,
        name: str,
        ref: str = "latest",
        variables: dict[str, str] | None = None,
    ) -> str:
        """Resolve *ref* and return the content with variables substituted."""
        engine = self._engine

        def _sync() -> str:
            version = self._s.resolve(namespace, name, ref)
            return engine.render_with_defaults(version.content, version.variables, variables)

        return await asyncio.to_thread(_sync)


class _Branches:
    """Async façade for branch operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(self, namespace: str, name: str, branch_name: str, from_sha: str) -> Branch:
        """Create *branch_name* for *namespace/name* starting from *from_sha*."""

        def _sync() -> Branch:
            return self._s.create_branch(
                _require_prompt_id(self._s, namespace, name), branch_name, from_sha
            )

        return await asyncio.to_thread(_sync)

    async def get(self, namespace: str, name: str, branch_name: str) -> Branch | None:
        """Return *branch_name* for *namespace/name*, or ``None`` if absent."""
        def _sync() -> Branch | None:
            return self._s.get_branch(_require_prompt_id(self._s, namespace, name), branch_name)

        return await asyncio.to_thread(_sync)

    async def list(self, namespace: str, name: str) -> builtins.list[Branch]:
        """Return all branches for *namespace/name*."""

        def _sync() -> builtins.list[Branch]:
            return self._s.list_branches(_require_prompt_id(self._s, namespace, name))

        return await asyncio.to_thread(_sync)

    async def merge(
        self, namespace: str, name: str, from_branch: str, into_branch: str = "main"
    ) -> Version:
        """Merge *from_branch* into *into_branch* for *namespace/name*."""
        return await asyncio.to_thread(self._s.merge, namespace, name, from_branch, into_branch)

    async def rollback(self, namespace: str, name: str, ref: str, branch: str = "main") -> Version:
        """Rollback *branch* for *namespace/name* to the version at *ref*."""
        return await asyncio.to_thread(self._s.rollback, namespace, name, ref, branch)


class _Tags:
    """Async façade for tag operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(self, namespace: str, name: str, tag_name: str, sha: str) -> Tag:
        """Create *tag_name* pointing to *sha* for *namespace/name*."""

        def _sync() -> Tag:
            return self._s.create_tag(_require_prompt_id(self._s, namespace, name), tag_name, sha)

        return await asyncio.to_thread(_sync)

    async def get(self, namespace: str, name: str, tag_name: str) -> Tag | None:
        """Return the tag *tag_name* for *namespace/name*, or ``None`` if absent."""
        def _sync() -> Tag | None:
            return self._s.get_tag(_require_prompt_id(self._s, namespace, name), tag_name)

        return await asyncio.to_thread(_sync)

    async def list(self, namespace: str, name: str) -> builtins.list[Tag]:
        """Return all tags for *namespace/name*."""

        def _sync() -> builtins.list[Tag]:
            return self._s.list_tags(_require_prompt_id(self._s, namespace, name))

        return await asyncio.to_thread(_sync)


class _Diff:
    """Async façade for diff operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def compute(self, sha1: str, sha2: str) -> str:
        """Return a unified-diff string comparing the content of *sha1* and *sha2*."""
        return await asyncio.to_thread(self._s.diff, sha1, sha2)


class _Forks:
    """Async façade for fork operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(
        self,
        source_namespace: str,
        source_name: str,
        dest_namespace: str,
        dest_name: str,
        branch: str = "main",
    ) -> Fork:
        """Fork *source_namespace/source_name* into *dest_namespace/dest_name*."""
        return await asyncio.to_thread(
            self._s.fork, source_namespace, source_name, dest_namespace, dest_name, branch
        )

    async def list(self, namespace: str, name: str) -> builtins.list[Fork]:
        """Return all forks of *namespace/name*."""
        return await asyncio.to_thread(self._s.list_forks, namespace, name)


class _Stars:
    """Async façade for starring/unstarring prompts."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def star(self, namespace: str, name: str, actor: str) -> Star:
        """Star *namespace/name* on behalf of *actor*."""
        return await asyncio.to_thread(self._s.star_prompt, namespace, name, actor)

    async def unstar(self, namespace: str, name: str, actor: str) -> bool:
        """Remove *actor*'s star from *namespace/name*; return ``True`` if it existed."""
        return await asyncio.to_thread(self._s.unstar_prompt, namespace, name, actor)

    async def list(self, namespace: str, name: str) -> builtins.list[Star]:
        """Return all stars (stargazers) for *namespace/name*."""
        return await asyncio.to_thread(self._s.list_stargazers, namespace, name)


class _Comments:
    """Async façade for comment operations on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def add(
        self,
        namespace: str,
        name: str,
        body: str,
        author: str,
        version_sha: str | None = None,
    ) -> Comment:
        """Add a comment from *author* to *namespace/name* (optionally on *version_sha*)."""
        return await asyncio.to_thread(
            self._s.add_comment, namespace, name, body, author, version_sha
        )

    async def list(
        self,
        namespace: str,
        name: str,
        version_sha: str | None = None,
    ) -> builtins.list[Comment]:
        """Return comments for *namespace/name*, optionally filtered by *version_sha*."""
        return await asyncio.to_thread(self._s.list_comments, namespace, name, version_sha)

    async def delete(self, comment_id: str) -> bool:
        """Delete the comment with *comment_id*; return ``True`` if it existed."""
        return await asyncio.to_thread(self._s.delete_comment, comment_id)


class _Collections:
    """Async façade for collection (curated list of prompts) operations."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(self, namespace: str, name: str, description: str = "") -> Collection:
        """Create a new collection *namespace/name*."""
        return await asyncio.to_thread(self._s.create_collection, namespace, name, description)

    async def get(self, namespace: str, name: str) -> Collection | None:
        """Return the collection *namespace/name*, or ``None`` if absent."""
        return await asyncio.to_thread(self._s.get_collection, namespace, name)

    async def list(self, namespace: str | None = None) -> builtins.list[Collection]:
        """Return all collections, optionally restricted to *namespace*."""
        return await asyncio.to_thread(self._s.list_collections, namespace)

    async def delete(self, namespace: str, name: str) -> bool:
        """Delete collection *namespace/name*; return ``True`` if it existed."""
        return await asyncio.to_thread(self._s.delete_collection, namespace, name)

    async def add_item(self, namespace: str, name: str, prompt_slug: str) -> None:
        """Add *prompt_slug* to collection *namespace/name*."""
        await asyncio.to_thread(self._s.add_to_collection, namespace, name, prompt_slug)

    async def remove_item(self, namespace: str, name: str, prompt_slug: str) -> bool:
        """Remove *prompt_slug* from *namespace/name*; return ``True`` if it was present."""
        return await asyncio.to_thread(self._s.remove_from_collection, namespace, name, prompt_slug)

    async def list_items(self, namespace: str, name: str) -> builtins.list[Prompt]:
        """Return all prompts that belong to collection *namespace/name*."""
        return await asyncio.to_thread(self._s.list_collection_items, namespace, name)


class _Webhooks:
    """Async façade for webhook management on the local store."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create(
        self,
        url: str,
        secret: str,
        events: builtins.list[str] | None = None,
        namespace: str | None = None,
    ) -> Webhook:
        """Register a new webhook that POSTs to *url* signed with *secret*."""
        return await asyncio.to_thread(self._s.create_webhook, url, secret, events, namespace)

    async def list(self) -> builtins.list[Webhook]:
        """Return all registered webhooks."""
        return await asyncio.to_thread(self._s.list_webhooks)

    async def delete(self, webhook_id: str) -> bool:
        """Delete the webhook with *webhook_id*; return ``True`` if it existed."""
        return await asyncio.to_thread(self._s.delete_webhook, webhook_id)

    async def fire(self, event: str, payload: dict[str, Any]) -> None:
        """Dispatch *event* with *payload* to all matching registered webhooks."""
        await asyncio.to_thread(self._s.fire_webhooks, event, payload)


class _Auth:
    """Async façade for API-key (token) management."""

    __slots__ = ("_s",)

    def __init__(self, store: VersionStore) -> None:
        """Bind to *store*."""
        self._s = store

    async def create_token(self, name: str) -> TokenResult:
        """Generate and store a new API key named *name*; returns the raw key (shown once)."""
        raw_key, key_hash = generate_api_key()

        def _sync() -> TokenResult:
            token_id, created_at = self._s.create_api_key(name, key_hash)
            return TokenResult(id=token_id, name=name, key=raw_key, created_at=created_at)

        return await asyncio.to_thread(_sync)

    async def list_tokens(self) -> builtins.list[TokenInfo]:
        """Return metadata for all stored API keys (raw keys not included)."""
        rows = await asyncio.to_thread(self._s.list_api_keys)
        return [
            TokenInfo(id=id_, name=name, created_at=ca, last_used_at=lua)
            for id_, name, ca, lua in rows
        ]

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke the API key with *token_id*; return ``True`` if it existed."""
        return await asyncio.to_thread(self._s.revoke_api_key, token_id)


# ---------------------------------------------------------------------------
# Export / push
# ---------------------------------------------------------------------------


class _Export:
    """Incremental, streaming export and push for a local Cantica instance.

    ``to_json``  — async generator yielding NDJSON lines (bytes).
    ``push``     — stream ``to_json`` to a remote Cantica instance's
                   ``POST /v1/push`` endpoint, acquiring the write lock so
                   no local writes interleave with the push.
    ``ingest``   — consume an async byte stream (NDJSON), importing each
                   record while holding the write lock.
    """

    __slots__ = ("_s", "_lock")

    def __init__(self, store: VersionStore, lock: asyncio.Lock) -> None:
        """Bind to *store* and the shared write *lock*."""
        self._s = store
        self._lock = lock

    async def to_json(
        self,
        since: datetime | None = None,
        namespace: str | None = None,
    ) -> AsyncGenerator[bytes]:
        """Yield NDJSON records (bytes, each ending with ``\\n``).

        Emits: namespace records, then prompt records, then version records,
        then a checkpoint record with the max ``created_at`` seen.

        The version records are ordered ``created_at ASC`` so that parent
        versions always precede their children on the receiving end.
        """

        def _fetch() -> tuple[
            builtins.list[Namespace],
            builtins.list[Prompt],
            builtins.list[tuple[str, str, Version]],
        ]:
            namespaces = self._s.list_namespaces()
            if namespace is not None:
                namespaces = [n for n in namespaces if n.name == namespace]
            prompts: builtins.list[Prompt] = []
            for ns in namespaces:
                prompts.extend(self._s.list_prompts(ns.name))
            versions = self._s.list_all_versions_for_export(since=since, namespace=namespace)
            return namespaces, prompts, versions

        namespaces, prompts, versions = await asyncio.to_thread(_fetch)

        for ns in namespaces:
            rec: dict[str, Any] = {
                "type": "namespace",
                "name": ns.name,
                "description": ns.description or "",
            }
            yield (json.dumps(rec) + "\n").encode()

        for p in prompts:
            rec = {
                "type": "prompt",
                "namespace": p.namespace,
                "name": p.name,
                "description": p.description or "",
                "tags": p.tags,
                "model_hints": p.model_hints,
                "license": p.license,
                "visibility": p.visibility.value,
                "variables": [v.model_dump() for v in (p.variables or [])],
            }
            yield (json.dumps(rec) + "\n").encode()

        checkpoint: str | None = None
        for ns_name, prompt_name, ver in versions:
            rec = {
                "type": "version",
                "namespace": ns_name,
                "name": prompt_name,
                "sha": ver.sha,
                "content": ver.content,
                "message": ver.message,
                "author": ver.author,
                "branch": ver.branch,
                "parent_sha": ver.parent_sha,
                "created_at": ver.created_at.isoformat(),
                "variables": [v.model_dump() for v in (ver.variables or [])],
            }
            yield (json.dumps(rec) + "\n").encode()
            checkpoint = ver.created_at.isoformat()

            for tag_name in ver.tags or []:
                tag_rec: dict[str, Any] = {
                    "type": "tag",
                    "namespace": ns_name,
                    "name": prompt_name,
                    "tag_name": tag_name,
                    "sha": ver.sha,
                }
                yield (json.dumps(tag_rec) + "\n").encode()

        if checkpoint is not None:
            yield (json.dumps({"type": "checkpoint", "created_at": checkpoint}) + "\n").encode()

    async def push(
        self,
        target_url: str,
        api_key: str,
        since: datetime | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Stream this instance's data to a remote Cantica *target_url*.

        Acquires the local write lock for the duration so that no writes
        interleave while the export snapshot is being streamed.  Requires
        ``httpx`` (``pip install httpx``).
        """
        # Third party imports:
        import httpx

        async with self._lock:

            async def _body() -> AsyncGenerator[bytes]:
                async for chunk in self.to_json(since=since, namespace=namespace):
                    yield chunk

            push_url = target_url.rstrip("/") + "/push"
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    push_url,
                    content=_body(),
                    headers={
                        "Content-Type": "application/x-ndjson",
                        "X-API-Key": api_key,
                    },
                    timeout=300,
                )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def ingest(self, stream: AsyncIterator[bytes]) -> dict[str, Any]:
        """Consume a raw NDJSON byte stream, importing all records.

        Acquires the write lock for the entire ingest so no concurrent writes
        can interleave with incoming data.
        """
        async with self._lock:
            imported = 0
            skipped = 0
            errors: builtins.list[str] = []
            buf = bytearray()

            async for chunk in stream:
                buf.extend(chunk)
                while b"\n" in buf:
                    idx = buf.index(b"\n")
                    line = bytes(buf[:idx]).strip()
                    del buf[: idx + 1]
                    if not line:
                        continue
                    try:
                        record: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError as exc:
                        errors.append(f"invalid JSON: {exc}")
                        continue
                    try:
                        outcome = await self._ingest_record(record)
                    except Exception as exc:
                        errors.append(str(exc))
                        continue
                    if outcome == "imported":
                        imported += 1
                    elif outcome == "skipped":
                        skipped += 1

        return {"imported": imported, "skipped": skipped, "errors": errors}

    async def _ingest_record(self, record: dict[str, Any]) -> str:
        """Import a single NDJSON record; return ``'imported'``, ``'skipped'``, or ``'ignored'``."""
        rtype = record.get("type")

        if rtype == "namespace":
            await asyncio.to_thread(
                self._s.create_namespace, record["name"], record.get("description", "")
            )
            return "ignored"

        if rtype == "prompt":
            existing = await asyncio.to_thread(
                self._s.get_prompt, record["namespace"], record["name"]
            )
            if existing is not None:
                return "skipped"
            variables = [VariableSchema(**v) for v in record.get("variables", [])]
            await asyncio.to_thread(
                self._s.create_prompt,
                record["namespace"],
                record["name"],
                record.get("description", ""),
                tags=record.get("tags"),
                model_hints=record.get("model_hints"),
                license=record.get("license", "MIT"),
                visibility=Visibility(record.get("visibility", "public")),
                variables=variables,
            )
            return "imported"

        if rtype == "version":
            sha = record["sha"]
            already = await asyncio.to_thread(self._s.has_version, sha)
            if already:
                return "skipped"

            def _do_import() -> None:
                prompt = self._s.get_prompt(record["namespace"], record["name"])
                if prompt is None:
                    raise KeyError(f"prompt not found: {record['namespace']}/{record['name']}")
                variables = [VariableSchema(**v) for v in record.get("variables", [])]
                self._s.import_version(
                    prompt.id,
                    sha,
                    record["content"],
                    record["message"],
                    record["author"],
                    record["branch"],
                    record.get("parent_sha"),
                    datetime.fromisoformat(record["created_at"]),
                    variables=variables,
                )

            await asyncio.to_thread(_do_import)
            return "imported"

        if rtype == "tag":

            def _do_tag() -> str:
                prompt = self._s.get_prompt(record["namespace"], record["name"])
                if prompt is None:
                    return "skipped"
                if self._s.get_tag(prompt.id, record["tag_name"]) is not None:
                    return "skipped"
                self._s.create_tag(prompt.id, record["tag_name"], record["sha"])
                return "imported"

            return await asyncio.to_thread(_do_tag)

        return "ignored"  # checkpoint + unknown types


# ---------------------------------------------------------------------------
# Public shim
# ---------------------------------------------------------------------------


class CanticaShim:
    """Embed a local Cantica instance as a library inside any FastAPI project.

    All data-layer methods are async and run the synchronous SQLAlchemy
    operations in a thread pool via ``asyncio.to_thread``, so they are safe
    to ``await`` from any async context without blocking the event loop.

    Instantiate once, call ``mount(app)`` to wire the HTTP routes, and use
    ``lifespan()`` (or ``wrap_lifespan()``) to handle clean shutdown.

    Quick-start::

        from cantica.shim import CanticaShim

        shim = CanticaShim(vault_path="/path/to/vault")

        @asynccontextmanager
        async def lifespan(app):
            async with shim.lifespan():
                yield

        app = FastAPI(lifespan=lifespan)
        shim.mount(app)   # registers /api/v1/* routes

        # Programmatic access — no HTTP round-trip:
        await shim.namespaces.create("acme")
        prompt = await shim.prompts.create("acme", "my-prompt")
        version = await shim.versions.commit("acme", "my-prompt", "Hello {{name}}", "init", "alice")
        rendered = await shim.versions.render("acme", "my-prompt", variables={"name": "world"})
        branches = await shim.branches.list("acme", "my-prompt")
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        vault_path: Path | str | None = None,
        database_url: str | None = None,
    ) -> None:
        """Initialise the shim, creating the vault directory and opening the store.

        Provide either a pre-built *settings* object or the individual keyword
        arguments *vault_path* and/or *database_url*.
        """
        if settings is None:
            settings = Settings(
                **({} if vault_path is None else {"vault_path": Path(vault_path)}),
                **({} if database_url is None else {"database_url": database_url}),
            )

        self._settings = settings
        settings.vault_path.mkdir(parents=True, exist_ok=True)
        self._store = VersionStore(
            settings.vault_path,
            database_url=settings.database_url or None,
        )
        self._write_lock = asyncio.Lock()

        _engine = TemplateEngine()
        self.namespaces = _Namespaces(self._store)
        self.prompts = _Prompts(self._store)
        self.versions = _Versions(self._store, _engine)
        self.branches = _Branches(self._store)
        self.tags = _Tags(self._store)
        self.diff = _Diff(self._store)
        self.forks = _Forks(self._store)
        self.stars = _Stars(self._store)
        self.comments = _Comments(self._store)
        self.collections = _Collections(self._store)
        self.webhooks = _Webhooks(self._store)
        self.auth = _Auth(self._store)
        self.export = _Export(self._store, self._write_lock)

    @property
    def store(self) -> VersionStore:
        """Direct access to the underlying VersionStore for advanced use."""
        return self._store

    def mount(self, app: FastAPI, prefix: str = "/api/v1") -> None:
        """Include Cantica routes in *app* and bind this shim's store and settings.

        Call this before the app starts handling requests (e.g. at module level
        or inside a lifespan, but before ``yield``).
        """
        # Local imports:
        from cantica.api.deps import get_store, get_write_lock
        from cantica.config import get_settings

        app.dependency_overrides[get_store] = lambda: self._store
        app.dependency_overrides[get_settings] = lambda: self._settings
        app.dependency_overrides[get_write_lock] = lambda: self._write_lock
        app.include_router(_api_router, prefix=prefix)

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Async context manager — closes the store on exit.

        Use inside a FastAPI ``lifespan`` function::

            @asynccontextmanager
            async def lifespan(app):
                async with shim.lifespan():
                    yield
        """
        try:
            yield
        finally:
            self._store.close()

    def wrap_lifespan(
        self,
        existing: Callable[..., Any] | None = None,
    ) -> Callable[[FastAPI], Any]:
        """Compose Cantica teardown with an existing FastAPI lifespan.

        *existing* must be an async-context-manager factory that accepts the
        FastAPI ``app`` as its sole argument (the standard lifespan signature).
        Returns a new lifespan factory suitable for ``FastAPI(lifespan=...)``.
        """
        shim_lifespan = self.lifespan

        @asynccontextmanager
        async def _combined(app: FastAPI) -> AsyncIterator[None]:
            async with shim_lifespan():
                if existing is not None:
                    async with existing(app):
                        yield
                else:
                    yield

        return _combined

    def close(self) -> None:
        """Close the underlying store and release the database connection."""
        self._store.close()
