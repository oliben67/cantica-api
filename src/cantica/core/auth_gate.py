"""Flag vocabulary, the flag-aware auth gate, and key-assertion verification.

Mirrors studio-api's auth/flags.py + auth/keyauth.py so both servers share
semantics and claim formats (one client key pair can serve both). External
auth failures are ONE generic message; the real reason goes to the
``cantica.audit`` logger.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

# Third party imports:
import jwt

if TYPE_CHECKING:
    # Local imports:
    from cantica.orm.tables import UserOrm

audit_log = logging.getLogger("cantica.audit")

FLAG_NEWBIE = "newbie"
FLAG_OK = "ok"
FLAG_PENDING_ROLES = "pending:roles"

WARNING_FLAGS = frozenset({"warning:abuse", "warning:suspicious", "warning:none"})
BLOCKED_FLAGS = frozenset({"blocked:abuse", "blocked:suspicious", "blocked:none"})

KNOWN_FLAGS = frozenset({FLAG_NEWBIE, FLAG_OK, FLAG_PENDING_ROLES} | WARNING_FLAGS | BLOCKED_FLAGS)

GENERIC_AUTH_FAILURE = "Not authenticated — contact your Cantica administrator"

ASSERTION_ALGORITHM = "RS256"


@dataclass
class GateResult:
    """Outcome of the flag gate for one user (spec AUTH F)."""

    allowed: bool
    warnings: list[str] = field(default_factory=list)
    audit_reason: str = ""


def gate_user(user: UserOrm | None, flags: dict[str, str], *, context: str) -> GateResult:
    """Evaluate spec AUTH F for *user* with *flags* ({flag: comment})."""
    if user is None:
        audit_log.warning("auth denied [%s]: user not found", context)
        return GateResult(allowed=False, audit_reason="not found")

    blocked = sorted(set(flags) & BLOCKED_FLAGS)
    warnings = sorted(set(flags) & WARNING_FLAGS)

    if blocked:
        detail = "; ".join(f"{b} ({flags[b]})" if flags[b] else b for b in blocked)
        state = "active" if user.is_active else "inactive"
        audit_log.warning(
            "auth denied [%s]: user=%s %s, blocked: %s", context, user.id, state, detail
        )
        return GateResult(allowed=False, audit_reason=f"blocked ({state}): {detail}")

    if not user.is_active:
        audit_log.warning("auth denied [%s]: user=%s inactive", context, user.id)
        return GateResult(allowed=False, audit_reason="inactive")

    if warnings:
        audit_log.info(
            "auth warning [%s]: user=%s carries %s", context, user.id, ", ".join(warnings)
        )
        return GateResult(allowed=True, warnings=warnings)

    return GateResult(allowed=True)


# ── Key assertions (shared claim format with studio-api) ──────────────────────


class KeyAssertionError(Exception):
    """Verification failure — callers translate to a generic 401."""


def reject_private_key_material(pem: str) -> None:
    """Refuse anything that looks like a private key — public keys only."""
    if "PRIVATE KEY" in pem:
        raise KeyAssertionError("private key material submitted")
    if "PUBLIC KEY" not in pem:
        raise KeyAssertionError("not a PEM public key")


def verify_assertion(assertion: str, public_key_pem: str, *, max_age_seconds: int) -> dict:
    """Verify an RS256 client assertion; return its payload.

    Enforces signature, exp (via PyJWT), iat freshness (with 30s leeway), and
    requires a jti claim. Raises KeyAssertionError on any failure.
    """
    try:
        payload = jwt.decode(
            assertion,
            public_key_pem,
            algorithms=[ASSERTION_ALGORITHM],
            options={"verify_aud": False},
            leeway=30,
        )
    except jwt.InvalidTokenError as exc:
        raise KeyAssertionError(f"assertion invalid: {exc}") from exc

    iat = payload.get("iat")
    if iat is None:
        raise KeyAssertionError("assertion missing iat")
    issued = datetime.fromtimestamp(float(iat), tz=UTC)
    now = datetime.now(UTC)
    if issued < now - timedelta(seconds=max_age_seconds) or issued > now + timedelta(seconds=30):
        raise KeyAssertionError("assertion outside freshness window")

    if not payload.get("jti"):
        raise KeyAssertionError("assertion missing jti")

    return payload
