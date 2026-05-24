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
    return _hash(raw)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
