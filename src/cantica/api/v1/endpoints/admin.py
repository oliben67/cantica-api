"""
FastAPI endpoints for administrator user management.

Router prefix: ``/v1/admin``   Tag: ``admin``
All endpoints require the ``admin`` role.

Endpoints
---------
``GET    /v1/admin/users``          List all users.
``POST   /v1/admin/users``          Create a new user.
``GET    /v1/admin/users/{id}``     Retrieve a user.
``PATCH  /v1/admin/users/{id}``     Update user fields (email, password, roles, is_active).
``DELETE /v1/admin/users/{id}``     Hard-delete a user.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import bcrypt
from fastapi import APIRouter, HTTPException, Request

# Local imports:
from cantica.api.deps import AdminUserDep, StoreDep, UserDep
from cantica.config import get_settings
from cantica.core.mailer import send_invite
from cantica.schemas.admin import InviteCreate, InviteResponse, UserAdminResponse, UserCreate, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_response(user) -> UserAdminResponse:  # type: ignore[no-untyped-def]
    return UserAdminResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=[r.value for r in user.roles],
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[UserAdminResponse])
def list_users(store: StoreDep, _admin: AdminUserDep) -> list[UserAdminResponse]:
    """List all registered users."""
    return [_to_response(u) for u in store.list_users()]


@router.post("/users", response_model=UserAdminResponse, status_code=201)
def create_user(body: UserCreate, store: StoreDep, _admin: AdminUserDep) -> UserAdminResponse:
    """Create a new user with a bcrypt-hashed password."""
    if store.get_user_by_username(body.username) is not None:
        raise HTTPException(status_code=409, detail=f"Username {body.username!r} already taken")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = store.create_user(
        username=body.username,
        email=body.email,
        password_hash=pw_hash,
        roles=body.roles,
    )
    return _to_response(user)


@router.get("/users/{user_id}", response_model=UserAdminResponse)
def get_user(user_id: str, store: StoreDep, _admin: AdminUserDep) -> UserAdminResponse:
    """Retrieve a user by ID."""
    row = store.get_user_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_response(store.orm_to_user(row))


@router.patch("/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: str, body: UserUpdate, store: StoreDep, _admin: AdminUserDep
) -> UserAdminResponse:
    """Partially update a user record."""
    pw_hash: str | None = None
    if body.password is not None:
        pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = store.update_user(
        user_id,
        email=body.email,
        password_hash=pw_hash,
        roles=body.roles,
        is_active=body.is_active,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_response(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, store: StoreDep, _admin: AdminUserDep) -> None:
    """Hard-delete a user."""
    if not store.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")


# ── Invites ────────────────────────────────────────────────────────────────


def _invite_url(request: Request, token: str) -> str:
    settings = get_settings()
    base = settings.base_url.rstrip("/") if settings.base_url else str(request.base_url).rstrip("/")
    return f"{base}/invite?token={token}"


@router.post("/invites", response_model=InviteResponse, status_code=201)
def create_invite(
    body: InviteCreate,
    request: Request,
    store: StoreDep,
    admin: AdminUserDep,
) -> InviteResponse:
    """Create a one-time invite link (and send email if SMTP is configured)."""
    settings = get_settings()
    invite = store.create_invite(
        email=body.email,
        created_by=admin.id,
        expires_in_hours=body.expires_in_hours,
    )
    url = _invite_url(request, invite["token"])
    send_invite(
        to_email=body.email,
        invite_url=url,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        smtp_from=settings.smtp_from,
        smtp_tls=settings.smtp_tls,
    )
    return InviteResponse(
        id=invite["id"],
        email=invite["email"],
        token=invite["token"],
        invite_url=url,
        expires_at=invite["expires_at"],
        used=invite["used"],
        created_at=invite["created_at"],
    )


@router.get("/invites", response_model=list[InviteResponse])
def list_invites(request: Request, store: StoreDep, _admin: AdminUserDep) -> list[InviteResponse]:
    """List all invites."""
    return [
        InviteResponse(
            id=inv["id"],
            email=inv["email"],
            token=inv["token"],
            invite_url=_invite_url(request, inv["token"]),
            expires_at=inv["expires_at"],
            used=inv["used"],
            created_at=inv["created_at"],
        )
        for inv in store.list_invites()
    ]
