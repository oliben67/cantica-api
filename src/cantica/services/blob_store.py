# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import hashlib
from pathlib import Path


class BlobStore:
    """Content-addressable store: SHA256(content) → blob file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: str) -> str:
        sha = hashlib.sha256(content.encode()).hexdigest()
        path = self._path(sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        return sha

    def get(self, sha: str) -> str:
        path = self._path(sha)
        if not path.exists():
            raise KeyError(f"blob {sha!r} not found")
        return path.read_text(encoding="utf-8")

    def exists(self, sha: str) -> bool:
        return self._path(sha).exists()

    def _path(self, sha: str) -> Path:
        # git-style two-char fanout directory
        return self.root / sha[:2] / sha[2:]
