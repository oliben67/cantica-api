"""
Domain models for users, roles, and auth configuration.

Models
------
Role        — string enum: admin, user, readonly, anonymous.
User        — authenticated or anonymous principal with roles.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import uuid
from datetime import UTC, datetime
from enum import StrEnum

# Third party imports:
from pydantic import BaseModel, Field


class Role(StrEnum):
    """User role controlling access to the API."""

    admin = "admin"
    user = "user"
    readonly = "readonly"
    anonymous = "anonymous"


class User(BaseModel):
    """Authenticated (or anonymous) principal."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str = ""
    roles: list[Role] = Field(default_factory=list)
    is_active: bool = True
    namespaces: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def has_role(self, *roles: Role) -> bool:
        """Return True if the user holds any of the given *roles*."""
        return any(r in self.roles for r in roles)

    def is_admin(self) -> bool:
        """Return True if the user is an administrator."""
        return Role.admin in self.roles

    def can_write(self) -> bool:
        """Return True if the user can create or modify resources."""
        return Role.admin in self.roles or Role.user in self.roles

    def can_read_private(self) -> bool:
        """Return True if the user can read private or unlisted prompts."""
        return Role.admin in self.roles or Role.user in self.roles
