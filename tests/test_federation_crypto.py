"""Tests for cantica.core.federation_crypto — all eight public functions."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest

# Local imports:
from cantica.core.federation_crypto import (
    decrypt_field,
    decrypt_from,
    derive_encryption_key,
    encrypt_field,
    encrypt_for,
    generate_key_pair,
    sign_message,
    verify_signature,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def key_pair() -> tuple[str, str]:
    """Generate one RSA-4096 key pair shared across the module (slow op)."""
    return generate_key_pair()


@pytest.fixture(scope="module")
def second_key_pair() -> tuple[str, str]:
    return generate_key_pair()


# ── generate_key_pair ─────────────────────────────────────────────────────────


def test_generate_key_pair_returns_pem_strings(key_pair: tuple[str, str]) -> None:
    pub, priv = key_pair
    assert pub.startswith("-----BEGIN PUBLIC KEY-----")
    assert priv.startswith("-----BEGIN RSA PRIVATE KEY-----")


def test_generate_key_pair_produces_unique_pairs() -> None:
    pub1, priv1 = generate_key_pair()
    pub2, priv2 = generate_key_pair()
    assert pub1 != pub2
    assert priv1 != priv2


# ── sign_message / verify_signature ──────────────────────────────────────────


def test_sign_and_verify_roundtrip(key_pair: tuple[str, str]) -> None:
    pub, priv = key_pair
    data = b"hello cantica federation"
    sig = sign_message(data, priv)
    assert isinstance(sig, str)
    assert verify_signature(data, sig, pub) is True


def test_verify_wrong_data_returns_false(key_pair: tuple[str, str]) -> None:
    pub, priv = key_pair
    sig = sign_message(b"original data", priv)
    assert verify_signature(b"tampered data", sig, pub) is False


def test_verify_wrong_key_returns_false(
    key_pair: tuple[str, str], second_key_pair: tuple[str, str]
) -> None:
    pub1, priv1 = key_pair
    pub2, _priv2 = second_key_pair
    sig = sign_message(b"some data", priv1)
    assert verify_signature(b"some data", sig, pub2) is False


def test_verify_corrupted_signature_returns_false(key_pair: tuple[str, str]) -> None:
    pub, _priv = key_pair
    assert verify_signature(b"data", "not-a-real-signature====", pub) is False


# ── encrypt_for / decrypt_from ────────────────────────────────────────────────


def test_encrypt_decrypt_roundtrip(key_pair: tuple[str, str]) -> None:
    pub, priv = key_pair
    plaintext = b"secret federation payload"
    encrypted = encrypt_for(plaintext, pub)
    assert isinstance(encrypted, str)
    recovered = decrypt_from(encrypted, priv)
    assert recovered == plaintext


def test_encrypt_produces_different_ciphertext_each_call(key_pair: tuple[str, str]) -> None:
    pub, _priv = key_pair
    e1 = encrypt_for(b"same plaintext", pub)
    e2 = encrypt_for(b"same plaintext", pub)
    assert e1 != e2  # ephemeral AES key + random nonce


def test_decrypt_with_wrong_private_key_raises(
    key_pair: tuple[str, str], second_key_pair: tuple[str, str]
) -> None:
    pub1, _priv1 = key_pair
    _pub2, priv2 = second_key_pair
    encrypted = encrypt_for(b"secret", pub1)
    with pytest.raises(Exception):
        decrypt_from(encrypted, priv2)


def test_encrypt_empty_bytes(key_pair: tuple[str, str]) -> None:
    pub, priv = key_pair
    assert decrypt_from(encrypt_for(b"", pub), priv) == b""


# ── derive_encryption_key ─────────────────────────────────────────────────────


def test_derive_encryption_key_length(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    key = derive_encryption_key(priv)
    assert len(key) == 32


def test_derive_encryption_key_deterministic(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    assert derive_encryption_key(priv) == derive_encryption_key(priv)


def test_derive_encryption_key_differs_across_key_pairs(
    key_pair: tuple[str, str], second_key_pair: tuple[str, str]
) -> None:
    _pub1, priv1 = key_pair
    _pub2, priv2 = second_key_pair
    assert derive_encryption_key(priv1) != derive_encryption_key(priv2)


# ── encrypt_field / decrypt_field ─────────────────────────────────────────────


def test_encrypt_decrypt_field_roundtrip(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    key = derive_encryption_key(priv)
    plaintext = "hello world"
    encrypted = encrypt_field(plaintext, key)
    assert isinstance(encrypted, str)
    assert decrypt_field(encrypted, key) == plaintext


def test_encrypt_field_nonce_randomness(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    key = derive_encryption_key(priv)
    e1 = encrypt_field("same", key)
    e2 = encrypt_field("same", key)
    assert e1 != e2  # random nonce per call


def test_decrypt_field_wrong_key_raises(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    key1 = derive_encryption_key(priv)
    key2 = b"\x00" * 32
    encrypted = encrypt_field("secret", key1)
    with pytest.raises(Exception):
        decrypt_field(encrypted, key2)


def test_encrypt_decrypt_field_unicode(key_pair: tuple[str, str]) -> None:
    _pub, priv = key_pair
    key = derive_encryption_key(priv)
    text = "Cantica fédération ✓"
    assert decrypt_field(encrypt_field(text, key), key) == text
