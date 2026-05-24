"""
API key generation and hashing utilities.

Cantica uses static API keys for authentication when ``CANTICA_AUTH_ENABLED``
is true.  Keys are generated with ``secrets.token_urlsafe(32)`` (256 bits of
cryptographic randomness), then immediately hashed with SHA-256 before
storage.  The raw key is shown to the user exactly once and is never persisted.

Functions
---------
``generate_api_key() -> (raw_key, key_hash)``
    Generate a fresh API key pair.  Callers store ``key_hash`` in the
    database and return ``raw_key`` to the user.

``hash_api_key(raw) -> key_hash``
    Deterministically hash a raw key for lookup or revocation checks.  Used
    by ``get_current_user`` in ``api/deps.py`` when verifying incoming
    ``X-API-Key`` header values.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import hashlib
import secrets


def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, key_hash). Only raw_key is shown to the user; store key_hash."""
    raw = secrets.token_urlsafe(32)
    return raw, _hash(raw)


def hash_api_key(raw: str) -> str:
    """Return the SHA-256 hex digest of *raw* for storage and lookup."""
    return _hash(raw)


def _hash(value: str) -> str:
    """Return the SHA-256 hex digest of *value*."""
    return hashlib.sha256(value.encode()).hexdigest()
