"""
Namespace access certificate utilities.

A certificate is a self-contained, HMAC-SHA256-signed token that grants the
holder access to a proprietary Cantica namespace.  Tokens are issued by the
Cantica instance that owns the namespace and verified by that same instance
using a per-instance signing secret stored in ``InstanceConfigOrm``.

Token format
------------
``<base64url(json_payload)>.<base64url(hmac_sha256(payload_bytes, secret))>``

The JSON payload fields:
- ``id``          — UUID, matches the ``NamespaceCertOrm.id`` record.
- ``namespace``   — namespace this certificate grants access to.
- ``granted_to``  — user/client identifier the cert was issued for.
- ``issued_at``   — ISO-8601 UTC timestamp.
- ``expires_at``  — ISO-8601 UTC timestamp or ``null`` (no expiry).

Verification checks:
1. HMAC signature matches (timing-safe comparison).
2. ``expires_at`` not in the past.
3. Revocation status is checked externally (in ``VersionStore``).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class CertPayload:
    """Decoded payload from a verified namespace access certificate token."""

    id: str
    namespace: str
    granted_to: str
    issued_at: datetime
    expires_at: datetime | None


def generate_token(
    cert_id: str,
    namespace: str,
    granted_to: str,
    issued_at: datetime,
    expires_at: datetime | None,
    secret: str,
) -> str:
    """Build and sign a certificate token string."""
    payload = {
        "id": cert_id,
        "namespace": namespace,
        "granted_to": granted_to,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{payload_b64}.{sig_b64}"


def verify_token(token: str, secret: str) -> CertPayload | None:
    """Parse and verify a certificate token.  Returns ``None`` on any failure.

    Does NOT check revocation — callers must look up the cert ID in the DB.
    """
    try:
        payload_b64, sig_b64 = token.rsplit(".", 1)
    except ValueError:
        return None

    # Re-add padding stripped during generation
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
    except Exception:  # pragma: no cover
        return None

    expected_sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).digest()
    padding2 = "=" * (-len(sig_b64) % 4)
    try:
        actual_sig = base64.urlsafe_b64decode(sig_b64 + padding2)
    except Exception:
        return None

    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    try:
        data = json.loads(payload_bytes)
        expires_raw = data.get("expires_at")
        expires_at = datetime.fromisoformat(expires_raw) if expires_raw else None
        if expires_at and datetime.now(UTC) > expires_at:
            return None
        return CertPayload(
            id=data["id"],
            namespace=data["namespace"],
            granted_to=data["granted_to"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=expires_at,
        )
    except Exception:
        return None


def generate_instance_secret() -> str:
    """Generate a random 32-byte hex secret for signing certificates."""
    return uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars = 32 bytes
