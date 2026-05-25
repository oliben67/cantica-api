# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import UTC, datetime, timedelta

# Local imports:
from cantica.core.certificates import CertPayload, generate_token, verify_token

SECRET = "a" * 64  # 64 hex chars = 32 bytes


def _make_cert(
    namespace: str = "acme",
    granted_to: str = "alice",
    expires_at: datetime | None = None,
    cert_id: str = "test-cert-id",
) -> str:
    return generate_token(
        cert_id=cert_id,
        namespace=namespace,
        granted_to=granted_to,
        issued_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        expires_at=expires_at,
        secret=SECRET,
    )


def test_generate_and_verify_roundtrip() -> None:
    token = _make_cert()
    payload = verify_token(token, SECRET)
    assert payload is not None
    assert isinstance(payload, CertPayload)
    assert payload.namespace == "acme"
    assert payload.granted_to == "alice"
    assert payload.id == "test-cert-id"
    assert payload.expires_at is None


def test_verify_with_wrong_secret_returns_none() -> None:
    token = _make_cert()
    assert verify_token(token, "b" * 64) is None


def test_verify_expired_token_returns_none() -> None:
    past = datetime(2000, 1, 1, tzinfo=UTC)
    token = _make_cert(expires_at=past)
    assert verify_token(token, SECRET) is None


def test_verify_future_expiry_succeeds() -> None:
    future = datetime.now(UTC) + timedelta(days=365)
    token = _make_cert(expires_at=future)
    payload = verify_token(token, SECRET)
    assert payload is not None
    assert payload.expires_at is not None


def test_verify_malformed_token_no_dot() -> None:
    assert verify_token("nodot", SECRET) is None


def test_verify_malformed_payload_bad_base64() -> None:
    assert verify_token("!!!.sig", SECRET) is None


def test_verify_malformed_sig_bad_base64() -> None:
    # Standard library imports:
    import base64
    import json

    payload = {
        "id": "x",
        "namespace": "ns",
        "granted_to": "u",
        "issued_at": "2024-01-01T00:00:00+00:00",
        "expires_at": None,
    }
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    assert verify_token(f"{b64}.!!!", SECRET) is None


def test_verify_invalid_json_payload() -> None:
    # Standard library imports:
    import base64
    import hashlib
    import hmac

    bad = base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode()
    sig = hmac.new(SECRET.encode(), b"not json", hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    assert verify_token(f"{bad}.{sig_b64}", SECRET) is None
