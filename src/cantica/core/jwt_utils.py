"""
JWT session token utilities.

``create_jwt``   — encode a User into a signed HS256 JWT.
``verify_jwt``   — decode and validate a JWT; returns User or None.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import UTC, datetime, timedelta

# Third party imports:
import jwt

# Local imports:
from cantica.models.user import Role, User


def create_jwt(user: User, secret: str, expire_minutes: int = 60) -> str:
    """Return a signed HS256 JWT encoding *user*'s identity and roles."""
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "roles": [r.value for r in user.roles],
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt(token: str, secret: str) -> User | None:
    """Decode *token* and return the embedded User, or None on any error."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return User(
            id=payload["sub"],
            username=payload["username"],
            email=payload.get("email", ""),
            roles=[Role(r) for r in payload.get("roles", [])],
        )
    except Exception:  # noqa: BLE001
        return None
