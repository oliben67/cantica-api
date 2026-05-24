"""
Lock file support for pinning ``cantica://`` URIs to exact version SHAs.

A Cantica lock file (``cantica.lock`` by default) is a TOML document that
records the exact SHA for each prompt URI used by a project, enabling
reproducible builds.  It is analogous to ``package-lock.json`` or
``Pipfile.lock``.

File format (TOML)::

    [lock]
    cantica_version = "0.1"
    generated_at = "2026-01-01T00:00:00+00:00"

    [[prompts]]
    uri       = "cantica://osteck/architect@v1.0"
    namespace = "osteck"
    name      = "architect"
    ref       = "v1.0"
    sha       = "<full-64-char-sha>"
    locked_at = "2026-01-01T00:00:00+00:00"

Models
------
``LockEntry``  — Pydantic model for a single pinned URI entry.
``LockFile``   — Container for the lock metadata and the list of entries.

Functions
---------
``write_lock(lock, path)``  — Serialise a ``LockFile`` to a TOML file using ``tomli_w``.
``read_lock(path)``         — Deserialise a ``LockFile`` from a TOML file using
                              stdlib ``tomllib``.

Lifecycle (CLI)
---------------
``cantica lock <uri...>``    — resolves each URI and writes a new lock file.
``cantica install``          — reads the lock file and fetches any missing versions
                              into the local vault.
"""

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
    """A single pinned dependency in a lock file."""

    uri: str
    namespace: str
    name: str
    ref: str
    sha: str
    locked_at: datetime


class LockFile(BaseModel):
    """Top-level model representing the contents of a ``cantica.lock`` file."""

    cantica_version: str = "0.1"
    generated_at: datetime
    prompts: list[LockEntry]


def write_lock(lock: LockFile, path: Path) -> None:
    """Serialise *lock* to a TOML file at *path*."""
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
    """Parse a TOML lock file at *path* and return a ``LockFile`` model."""
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
