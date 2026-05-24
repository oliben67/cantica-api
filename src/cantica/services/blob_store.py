"""
Content-addressable blob store for prompt content (plain and AES-256-GCM encrypted).

``BlobStore`` stores arbitrary text strings keyed by their SHA-256 digest of the
**plaintext**, following the same two-character fanout layout used by git object
databases:

    <root>/
        <first-2-chars-of-sha>/
            <remaining-chars-of-sha>          ← unencrypted blob
            <remaining-chars-of-sha>.enc      ← AES-256-GCM encrypted blob

Unencrypted blobs are deduplicated: ``put()`` is a no-op if the blob already
exists.  Encrypted blobs always write a fresh nonce (so the ciphertext differs
even for identical plaintext — no deduplication for encoded namespaces).

``VersionStore`` is the only caller.  The ``is_encoded`` flag on ``VersionOrm``
determines which read path to use at retrieval time.  The 32-byte AES key (hex
string) is stored per-namespace in ``NamespaceOrm.encryption_key``.

Encrypted blob format (binary, stored as-is):
    12 bytes — random GCM nonce
    N bytes  — AES-256-GCM ciphertext + 16-byte authentication tag
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import hashlib
import os
from pathlib import Path

# Third party imports:
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class BlobStore:
    """Content-addressable store: SHA256(plaintext) → blob file."""

    def __init__(self, root: Path) -> None:
        """Initialise the store, creating the *root* directory if necessary."""
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: str) -> str:
        """Write *content* to the store and return its SHA-256 hex digest."""
        sha = hashlib.sha256(content.encode()).hexdigest()
        path = self._path(sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        return sha

    def get(self, sha: str) -> str:
        """Return the plaintext content for *sha*, raising ``KeyError`` if absent."""
        path = self._path(sha)
        if not path.exists():
            raise KeyError(f"blob {sha!r} not found")
        return path.read_text(encoding="utf-8")

    def put_encrypted(self, content: str, key_hex: str) -> str:
        """Encrypt *content* with AES-256-GCM and store it.  Returns SHA-256 of plaintext."""
        sha = hashlib.sha256(content.encode()).hexdigest()
        path = self._enc_path(sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        key = bytes.fromhex(key_hex)
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, content.encode(), None)
        path.write_bytes(nonce + ciphertext)
        return sha

    def get_encrypted(self, sha: str, key_hex: str) -> str:
        """Decrypt and return content for an encoded blob."""
        path = self._enc_path(sha)
        if not path.exists():
            raise KeyError(f"encrypted blob {sha!r} not found")
        raw = path.read_bytes()
        nonce, ciphertext = raw[:12], raw[12:]
        key = bytes.fromhex(key_hex)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()

    def exists(self, sha: str) -> bool:
        """Return ``True`` if the blob for *sha* exists in the store."""
        return self._path(sha).exists()

    def _path(self, sha: str) -> Path:
        """Return the filesystem path for a plaintext blob."""
        return self.root / sha[:2] / sha[2:]

    def _enc_path(self, sha: str) -> Path:
        """Return the filesystem path for an encrypted blob."""
        return self.root / sha[:2] / (sha[2:] + ".enc")
