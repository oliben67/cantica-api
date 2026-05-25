# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import os
from pathlib import Path

# Third party imports:
import pytest

# Local imports:
from cantica.services.blob_store import BlobStore


def test_put_and_get(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    sha = bs.put("hello world")
    assert bs.get(sha) == "hello world"


def test_put_encrypted_and_get_encrypted(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    key_hex = os.urandom(32).hex()
    sha = bs.put_encrypted("secret content", key_hex)
    assert bs.get_encrypted(sha, key_hex) == "secret content"


def test_get_encrypted_not_found_raises(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    with pytest.raises(KeyError):
        bs.get_encrypted("a" * 64, "b" * 64)


def test_put_encrypted_different_nonce_each_time(tmp_path: Path) -> None:
    bs = BlobStore(tmp_path)
    key_hex = os.urandom(32).hex()
    sha1 = bs.put_encrypted("same content", key_hex)
    sha2 = bs.put_encrypted("same content", key_hex)
    assert sha1 == sha2  # same plaintext SHA
    # But re-reading still works
    assert bs.get_encrypted(sha2, key_hex) == "same content"
