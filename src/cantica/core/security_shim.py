"""
cantica-secure adoption (extraction roadmap Phase C).

Builds the SecurityShim from Cantica settings and adapts its principal to
Cantica's ``User`` model, so domain endpoints and ``User`` call sites are
untouched when ``CANTICA_SECURITY_SHIM=1``. The in-repo security
implementation stays and remains the flag-off path.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from typing import TYPE_CHECKING

# Third party imports:
from cantica_secure import (
    CANTICA_PERMISSIONS,
    CANTICA_ROLES,
    CurrentUser,
    SecureConfig,
    SecurityShim,
)

# Local imports:
from cantica.models.user import Role, User

if TYPE_CHECKING:
    # Local imports:
    from cantica.config import Settings

_KNOWN_ROLES = {r.value for r in Role}


def to_cantica_user(principal: CurrentUser) -> User:
    """Map a cantica-secure principal onto Cantica's ``User`` model.

    Roles the shim reports that are not part of Cantica's enum (e.g. ``limbo``)
    are dropped; an authenticated principal with no mappable role still counts
    as ``user`` so it can write, while the anonymous principal keeps whatever
    anonymous roles were configured (typically ``readonly``).
    """
    roles = [Role(r) for r in principal.roles if r in _KNOWN_ROLES]
    if principal.is_anonymous and not roles:
        roles = [Role.anonymous]
    return User(
        id=principal.user_id,
        username=principal.email or ("anonymous" if principal.is_anonymous else principal.user_id),
        email=principal.email,
        roles=roles,
        is_active=True,
    )


def build_security_shim(settings: Settings) -> SecurityShim:
    """Map Cantica settings onto SecureConfig and construct the shim."""
    # The security DB lives beside the vault but is owned by the shim alone.
    secure_db = settings.vault_path / "secure" / "secure.db"
    config = SecureConfig(
        local_mode=not settings.auth_enabled,
        db_path=secure_db,
        jwt_secret=settings.jwt_secret or _derived_secret(settings),
        jwt_expire_minutes=settings.jwt_expire_minutes,
        auto_activate_users=settings.auto_activate_users,
        assertion_max_age_seconds=settings.assertion_max_age_seconds,
        admin_email=settings.secure_admin_email,
        admin_password=settings.secure_admin_password,
        # Cantica keeps anonymous read access (auth.yaml semantics).
        allow_anonymous=True,
        anonymous_roles_raw='["readonly"]',
        default_roles_raw='["user"]',
    )
    return SecurityShim(
        config,
        app_name="Cantica",
        permissions=CANTICA_PERMISSIONS,
        builtin_roles=CANTICA_ROLES,
        principal_adapter=to_cantica_user,
    )


def _derived_secret(settings: Settings) -> str:
    """Match the in-repo get_jwt_secret fallback so tokens survive the flag."""
    # Standard library imports:
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(str(settings.vault_path).encode()).hexdigest()
