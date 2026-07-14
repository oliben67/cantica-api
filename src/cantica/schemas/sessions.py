"""
Pydantic schemas for session (login/logout/me) endpoints.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Body for ``POST /v1/auth/login``."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Serialisable representation of the current user."""

    id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool


class SessionResponse(BaseModel):
    """Response body returned by a successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse
