"""
FastAPI endpoints for session management (login, logout, me).

Router prefix: ``/v1/auth``   Tag: ``auth``

Endpoints
---------
``POST /v1/auth/login``
    Authenticate with username + password.  Returns a signed JWT bearer token
    and the current user record.

``GET  /v1/auth/me``
    Return the currently authenticated user (identified by JWT or API key).

``POST /v1/auth/logout``
    Stateless logout: instructs the client to discard the token.  No server-side
    token invalidation (JWTs are short-lived; add a blacklist if needed).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, Depends, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep, get_auth_provider, get_jwt_secret
from cantica.core.jwt_utils import create_jwt
from cantica.models.user import User
from cantica.schemas.sessions import LoginRequest, SessionResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=[r.value for r in user.roles],
        is_active=user.is_active,
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest,
    store: StoreDep,
    auth_provider=Depends(get_auth_provider),
    jwt_secret: str = Depends(get_jwt_secret),
) -> SessionResponse:
    """Authenticate and return a JWT bearer token."""
    from cantica.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    user = await auth_provider.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt(user, jwt_secret, expire_minutes=settings.jwt_expire_minutes)
    return SessionResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: UserDep) -> UserResponse:
    """Return the authenticated user's profile."""
    return _user_response(user)


@router.post("/logout", status_code=204)
def logout(_user: UserDep) -> None:
    """Stateless logout: client should discard its token."""
