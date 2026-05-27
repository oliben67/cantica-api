"""
RSA-4096 key generation, signing, hybrid encryption, and at-rest field encryption.

Functions
---------
generate_key_pair       — generate RSA-4096 key pair
sign_message            — RSA-PSS sign bytes; returns base64 signature
verify_signature        — verify RSA-PSS signature
encrypt_for             — hybrid encrypt (AES-256-GCM + RSA-OAEP key wrap)
decrypt_from            — decrypt a hybrid-encrypted blob
derive_encryption_key   — HKDF-derive 32-byte AES key from private key PEM
encrypt_field           — AES-256-GCM encrypt a string for DB storage
decrypt_field           — decrypt a field produced by encrypt_field
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import base64
import os
import struct

# Third party imports:
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_KEY_SIZE = 4096  # RSA key size in bits


def generate_key_pair() -> tuple[str, str]:
    """Generate an RSA-4096 key pair.

    Returns ``(public_pem, private_pem)`` as PEM-encoded strings.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=_KEY_SIZE)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return public_pem, private_pem


def sign_message(data: bytes, private_pem: str) -> str:
    """RSA-PSS sign *data* with *private_pem*.

    Returns a base64-encoded signature string.
    """
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    signature = private_key.sign(  # type: ignore[union-attr]
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def verify_signature(data: bytes, signature_b64: str, public_pem: str) -> bool:
    """Verify an RSA-PSS *signature_b64* over *data* using *public_pem*.

    Returns ``True`` if the signature is valid, ``False`` otherwise.
    """
    public_key = serialization.load_pem_public_key(public_pem.encode())
    try:
        raw_sig = base64.b64decode(signature_b64)
        public_key.verify(  # type: ignore[union-attr]
            raw_sig,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def encrypt_for(plaintext: bytes, recipient_public_pem: str) -> str:
    """Hybrid-encrypt *plaintext* for *recipient_public_pem*.

    Uses AES-256-GCM for the payload and RSA-OAEP to wrap the ephemeral key.

    Blob format::

        [4B big-endian wrapped_key_len][wrapped_key][12B nonce][ciphertext+tag]

    Returns a base64-encoded blob.
    """
    public_key = serialization.load_pem_public_key(recipient_public_pem.encode())
    # Generate ephemeral AES-256 key
    aes_key = os.urandom(32)
    nonce = os.urandom(12)
    # Encrypt payload
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    # Wrap AES key with RSA-OAEP
    wrapped_key = public_key.encrypt(  # type: ignore[union-attr]
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    # Pack: 4B length prefix + wrapped_key + nonce + ciphertext+tag
    blob = struct.pack(">I", len(wrapped_key)) + wrapped_key + nonce + ciphertext
    return base64.b64encode(blob).decode()


def decrypt_from(encrypted_b64: str, private_pem: str) -> bytes:
    """Decrypt a blob produced by :func:`encrypt_for`.

    Raises ``ValueError`` on decryption failure.
    """
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    raw = base64.b64decode(encrypted_b64)
    # Unpack
    (wrapped_key_len,) = struct.unpack(">I", raw[:4])
    offset = 4
    wrapped_key = raw[offset : offset + wrapped_key_len]
    offset += wrapped_key_len
    nonce = raw[offset : offset + 12]
    offset += 12
    ciphertext = raw[offset:]
    # Unwrap AES key
    aes_key = private_key.decrypt(  # type: ignore[union-attr]
        wrapped_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    # Decrypt payload
    return AESGCM(aes_key).decrypt(nonce, ciphertext, None)


def derive_encryption_key(private_pem: str) -> bytes:
    """Derive a 32-byte AES-256 at-rest encryption key from *private_pem* via HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cantica-federation-v1",
        info=b"at-rest-encryption",
    )
    return hkdf.derive(private_pem.encode())


def encrypt_field(plaintext: str, key: bytes) -> str:
    """AES-256-GCM encrypt a string field for DB storage.

    Returns ``base64(nonce + ciphertext + tag)``.
    """
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_field(encrypted_b64: str, key: bytes) -> str:
    """Decrypt a field produced by :func:`encrypt_field`.

    Returns the plaintext string.  Raises on invalid key or tampered data.
    """
    raw = base64.b64decode(encrypted_b64)
    return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode()
