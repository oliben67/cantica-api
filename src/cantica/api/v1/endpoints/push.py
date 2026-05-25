# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import asyncio
import json
from datetime import datetime
from typing import Any

# Third party imports:
from fastapi import APIRouter, HTTPException, Request

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep, WriteLockDep
from cantica.models import VariableSchema, Visibility
from cantica.services.version_store import VersionStore

router = APIRouter(tags=["push"])


@router.post("/push")
async def receive_push(
    request: Request,
    store: StoreDep,
    _user: UserDep,
    lock: WriteLockDep,
    cert_token: CertTokenDep = None,
) -> dict[str, Any]:
    """Ingest a streaming NDJSON push from another Cantica instance.

    The request body must be ``application/x-ndjson``: one JSON record per
    line.  Supported record types: ``namespace``, ``prompt``, ``version``,
    ``tag``, ``checkpoint``.

    The write lock is held for the entire duration so that concurrent writes
    from an embedded shim do not interleave with the incoming data.
    """
    async with lock:
        imported = 0
        skipped = 0
        errors: list[str] = []
        buf = bytearray()

        async for chunk in request.stream():
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
                    outcome = await _ingest_record(store, record, cert_token)
                except Exception as exc:
                    errors.append(str(exc))
                    continue
                if outcome == "imported":
                    imported += 1
                elif outcome == "skipped":
                    skipped += 1

        if errors:
            raise HTTPException(
                status_code=422,
                detail={"imported": imported, "skipped": skipped, "errors": errors},
            )

    return {"imported": imported, "skipped": skipped}


async def _ingest_record(
    store: VersionStore, record: dict[str, Any], cert_token: str | None
) -> str:
    """Process one NDJSON record. Returns 'imported', 'skipped', or 'ignored'."""
    rtype = record.get("type")

    if rtype == "namespace":
        store.check_namespace_access(record["name"], cert_token)
        await asyncio.to_thread(
            store.create_namespace, record["name"], record.get("description", "")
        )
        return "ignored"

    if rtype == "prompt":
        store.check_namespace_access(record["namespace"], cert_token)
        existing = await asyncio.to_thread(store.get_prompt, record["namespace"], record["name"])
        if existing is not None:
            return "skipped"
        variables = [VariableSchema(**v) for v in record.get("variables", [])]
        await asyncio.to_thread(
            store.create_prompt,
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
        store.check_namespace_access(record["namespace"], cert_token)
        sha = record["sha"]
        already = await asyncio.to_thread(store.has_version, sha)
        if already:
            return "skipped"

        def _do_import() -> None:
            prompt = store.get_prompt(record["namespace"], record["name"])
            if prompt is None:
                raise KeyError(f"prompt not found: {record['namespace']}/{record['name']}")
            variables = [VariableSchema(**v) for v in record.get("variables", [])]
            store.import_version(
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
        store.check_namespace_access(record["namespace"], cert_token)

        def _do_tag() -> str:
            prompt = store.get_prompt(record["namespace"], record["name"])
            if prompt is None:
                return "skipped"
            if store.get_tag(prompt.id, record["tag_name"]) is not None:
                return "skipped"
            store.create_tag(prompt.id, record["tag_name"], record["sha"])
            return "imported"

        return await asyncio.to_thread(_do_tag)

    return "ignored"  # checkpoint + unknown types
