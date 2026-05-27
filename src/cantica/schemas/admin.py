"""
Pydantic schemas for the admin user-management API.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Body for ``POST /v1/admin/users``."""

    username: str
    email: str = ""
    password: str
    roles: list[str] = Field(default_factory=lambda: ["user"])


class UserUpdate(BaseModel):
    """Body for ``PATCH /v1/admin/users/{id}``.  All fields optional."""

    email: str | None = None
    password: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


class UserAdminResponse(BaseModel):
    """Full user record returned by the admin API."""

    id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool
    created_at: datetime


class PasswordChange(BaseModel):
    """Body for ``POST /v1/auth/password`` (self-service password change)."""

    current_password: str
    new_password: str


class InviteCreate(BaseModel):
    """Body for ``POST /v1/admin/invites``."""

    email: str
    expires_in_hours: int = 168  # 7 days


class InviteResponse(BaseModel):
    """Admin-visible invite record including the one-time token."""

    id: str
    email: str
    token: str
    invite_url: str
    expires_at: datetime
    used: bool
    created_at: datetime


class InviteAccept(BaseModel):
    """Body for ``POST /v1/invites/{token}/accept``."""

    username: str
    password: str
    email: str = ""


class InviteValidation(BaseModel):
    """Public response for ``GET /v1/invites/{token}``."""

    valid: bool
    email: str = ""
    message: str = ""
