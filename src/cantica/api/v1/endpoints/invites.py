"""
Public endpoints for invite-based user registration.

Router prefix: ``/v1/invites``   Tag: ``invites``
No authentication required — these are the public-facing invite flow endpoints.

Endpoints
---------
``GET  /v1/invites/{token}``         Validate a token (not expired, not used).
``POST /v1/invites/{token}/accept``  Create a user account and return a JWT.
"""

from __future__ import annotations

from datetime import UTC, datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException

from cantica.api.deps import StoreDep, get_jwt_secret
from cantica.core.jwt_utils import create_jwt
from cantica.schemas.admin import InviteAccept, InviteValidation
from cantica.schemas.sessions import SessionResponse, UserResponse

router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("/{token}", response_model=InviteValidation)
def validate_invite(token: str, store: StoreDep) -> InviteValidation:
    """Return whether the token is valid and unused."""
    invite = store.get_invite_by_token(token)
    if invite is None:
        return InviteValidation(valid=False, message="Invalid invite link")
    if invite["used_at"] is not None:
        return InviteValidation(valid=False, message="This invite has already been used")
    if invite["expires_at"] < datetime.now(UTC):
        return InviteValidation(valid=False, message="This invite has expired")
    return InviteValidation(valid=True, email=invite["email"])


@router.post("/{token}/accept", response_model=SessionResponse, status_code=201)
def accept_invite(
    token: str,
    body: InviteAccept,
    store: StoreDep,
    jwt_secret: str = Depends(get_jwt_secret),
) -> SessionResponse:
    """Validate the invite, create the user account, and return a JWT session."""
    from cantica.config import get_settings  # noqa: PLC0415

    invite = store.get_invite_by_token(token)
    if invite is None or invite["used_at"] is not None:
        raise HTTPException(status_code=400, detail="Invalid or already-used invite")
    if invite["expires_at"] < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Invite has expired")

    if store.get_user_by_username(body.username) is not None:
        raise HTTPException(status_code=409, detail=f"Username {body.username!r} already taken")

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    email = body.email or invite["email"]
    user = store.create_user(username=body.username, email=email, password_hash=pw_hash)
    store.use_invite(token, user.id)

    settings = get_settings()
    jwt_token = create_jwt(user, jwt_secret, expire_minutes=settings.jwt_expire_minutes)
    return SessionResponse(
        access_token=jwt_token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            roles=[r.value for r in user.roles],
            is_active=user.is_active,
        ),
    )
