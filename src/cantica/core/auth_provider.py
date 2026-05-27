"""
Authentication provider abstraction and local implementation.

``AuthProvider``      — Protocol (structural interface) every auth backend must satisfy.
``LocalAuthProvider`` — bcrypt password provider backed by the Cantica DB.

Pluggability
------------
Swap the backend by changing ``provider`` in ``auth.yaml`` and implementing
``AuthProvider``::

    provider: oidc
    oidc:
      issuer: https://sso.company.com
      client_id: cantica

Stubs for OIDC/LDAP are planned; the ``LocalAuthProvider`` is the only
production implementation for now.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from typing import TYPE_CHECKING, Protocol, runtime_checkable

# Third party imports:
import bcrypt

# Local imports:
from cantica.core.auth_config import AuthConfig
from cantica.models.user import Role, User

if TYPE_CHECKING:
    from cantica.services.version_store import VersionStore

_SETUP_BANNER = """
╔══════════════════════════════════════════════════════════════════════════╗
║              CANTICA — FIRST-INSTALL SETUP KEY                           ║
║                                                                          ║
║  A temporary admin account has been created for initial setup.           ║
║                                                                          ║
║  Username : admin                                                        ║
║  Setup key: {key}  ║
║                                                                          ║
║  Log in at /v1/auth/login and change the password immediately.           ║
║  This key will NOT be shown again.                                       ║
╚══════════════════════════════════════════════════════════════════════════╝"""


def _print_setup_banner(key: str) -> None:
    """Print the first-install setup key banner to stdout (once only)."""
    # Pad or trim so the key fits the fixed-width box
    padded = f"{key:<44}"
    print(_SETUP_BANNER.format(key=padded), flush=True)


@runtime_checkable
class AuthProvider(Protocol):
    """Structural interface every authentication backend must satisfy."""

    async def authenticate(self, username: str, password: str) -> User | None:
        """Return a User on success, None on bad credentials or inactive account."""
        ...

    async def get_user(self, user_id: str) -> User | None:
        """Return the User for *user_id*, or None if not found / inactive."""
        ...

    async def get_anonymous_user(self) -> User:
        """Return the User granted to unauthenticated callers."""
        ...

    async def bootstrap(self) -> None:
        """Idempotently seed provider-specific state (e.g. DB rows from YAML)."""
        ...


class LocalAuthProvider:
    """Username/password provider backed by the Cantica SQLite/PostgreSQL DB.

    On startup, ``bootstrap()`` imports any ``seed_users`` from ``auth.yaml``
    into the DB if they do not already exist.  After that the DB is the single
    source of truth; the YAML is not re-read at runtime.
    """

    def __init__(self, store: VersionStore, config: AuthConfig) -> None:
        self._store = store
        self._config = config

    async def bootstrap(self) -> None:
        """Seed users from ``auth.yaml`` into the DB; print a setup key on first install."""
        # Standard library imports:
        import secrets

        for seed in self._config.local.seed_users:
            if self._store.get_user_by_username(seed.username) is None:
                pw_hash = bcrypt.hashpw(seed.password.encode(), bcrypt.gensalt()).decode()
                self._store.create_user(
                    username=seed.username,
                    email=seed.email,
                    password_hash=pw_hash,
                    roles=seed.roles,
                )

        # First-install: no users and no seed config → generate a one-time setup key.
        if not self._store.list_users() and not self._config.local.seed_users:
            setup_key = f"cantica-setup-{secrets.token_urlsafe(32)}"
            pw_hash = bcrypt.hashpw(setup_key.encode(), bcrypt.gensalt()).decode()
            self._store.create_user(
                username="admin",
                email="",
                password_hash=pw_hash,
                roles=["admin"],
            )
            _print_setup_banner(setup_key)

    async def authenticate(self, username: str, password: str) -> User | None:
        """Verify *username* / *password* and return the corresponding User."""
        row = self._store.get_user_by_username(username)
        if row is None or not row.is_active:
            return None
        if not row.password_hash:
            return None
        if not bcrypt.checkpw(password.encode(), row.password_hash.encode()):
            return None
        return self._store.orm_to_user(row)

    async def get_user(self, user_id: str) -> User | None:
        """Return the User for *user_id*, or None."""
        row = self._store.get_user_by_id(user_id)
        if row is None or not row.is_active:
            return None
        return self._store.orm_to_user(row)

    async def get_anonymous_user(self) -> User:
        """Return the User representing an unauthenticated caller."""
        return User(
            id="anonymous",
            username="anonymous",
            roles=[Role(r) for r in self._config.anonymous.roles],
            is_active=True,
        )
