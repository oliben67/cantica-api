# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import tomllib
from datetime import UTC, datetime
from pathlib import Path

# Third party imports:
import tomli_w
from pydantic import BaseModel


class LockEntry(BaseModel):
    uri: str
    namespace: str
    name: str
    ref: str
    sha: str
    locked_at: datetime


class LockFile(BaseModel):
    cantica_version: str = "0.1"
    generated_at: datetime
    prompts: list[LockEntry]


def write_lock(lock: LockFile, path: Path) -> None:
    data: dict = {
        "lock": {
            "cantica_version": lock.cantica_version,
            "generated_at": lock.generated_at.isoformat(),
        },
        "prompts": [
            {
                "uri": e.uri,
                "namespace": e.namespace,
                "name": e.name,
                "ref": e.ref,
                "sha": e.sha,
                "locked_at": e.locked_at.isoformat(),
            }
            for e in lock.prompts
        ],
    }
    path.write_bytes(tomli_w.dumps(data).encode())


def read_lock(path: Path) -> LockFile:
    raw = tomllib.loads(path.read_text())
    meta = raw.get("lock", {})
    prompts = [
        LockEntry(
            uri=p["uri"],
            namespace=p["namespace"],
            name=p["name"],
            ref=p["ref"],
            sha=p["sha"],
            locked_at=datetime.fromisoformat(p["locked_at"]),
        )
        for p in raw.get("prompts", [])
    ]
    return LockFile(
        cantica_version=meta.get("cantica_version", "0.1"),
        generated_at=datetime.fromisoformat(
            meta.get("generated_at", datetime.now(UTC).isoformat())
        ),
        prompts=prompts,
    )
