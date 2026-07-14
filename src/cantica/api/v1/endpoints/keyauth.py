"""
Key-based authentication endpoints (remote-mode auth spec, phases 3–4).

Router prefix: ``/v1/auth``   Tag: ``keyauth``

Claim formats are shared with studio-api (RS256 assertions carrying
``iss``/``sub`` = cantica_user_id plus ``iat``/``exp``/``jti``), so one client
key pair serves both servers.

Endpoints
---------
``POST /v1/auth/register``  Enrol the caller's public key (requires a JWT
                            session, e.g. fresh from invite acceptance).
``POST /v1/auth/assert``    Exchange a key-signed assertion for a session JWT.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import UTC, datetime, timedelta

# Third party imports:
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# Local imports:
from cantica.api.deps import StoreDep, get_current_user, get_jwt_secret
from cantica.core.auth_gate import (
    GENERIC_AUTH_FAILURE,
    KeyAssertionError,
    audit_log,
    gate_user,
    reject_private_key_material,
    verify_assertion,
)
from cantica.core.jwt_utils import create_jwt
from cantica.models.user import Role, User

router = APIRouter(prefix="/auth", tags=["keyauth"])


class EnrolRequest(BaseModel):
    """Assertion signed with the caller's PRIVATE key + the matching PUBLIC key."""

    assertion: str
    public_key_pem: str


class AssertRequest(BaseModel):
    assertion: str


class AssertResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    warnings: list[str] = []


@router.post("/register", status_code=201)
def register_key(
    body: EnrolRequest,
    store: StoreDep,
    user: User = Depends(get_current_user),
) -> dict:
    """Enrol the authenticated caller's public key, bound to cantica_user_id."""
    # Local imports:
    from cantica.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.auth_enabled:
        return {"status": "ok", "mode": "local"}
    if user.id in ("anonymous", "local") or not user.id:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)

    row = store.get_user_by_id(user.id)
    if row is None:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)
    if store.user_has_active_jwt_key(user.id):
        audit_log.warning("enrolment denied: user=%s already enrolled", user.id)
        raise HTTPException(status_code=409, detail="A key is already enrolled — revoke it first")

    try:
        reject_private_key_material(body.public_key_pem)
        payload = verify_assertion(
            body.assertion,
            body.public_key_pem,
            max_age_seconds=settings.assertion_max_age_seconds,
        )
        if not store.burn_jti(
            payload["jti"],
            "enrol",
            datetime.now(UTC) + timedelta(seconds=settings.assertion_max_age_seconds),
        ):
            raise KeyAssertionError("jti replayed (enrol)")
    except KeyAssertionError as exc:
        audit_log.warning("enrolment denied [user=%s]: %s", user.id, exc)
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)

    cantica_user_id = row.e_user_id or row.email or row.username
    key_id = store.add_jwt_key(cantica_user_id, user.id, body.public_key_pem)
    audit_log.info(
        "key enrolled: user=%s cantica_user_id=%s key=%s", user.id, cantica_user_id, key_id
    )
    return {"status": "enrolled", "cantica_user_id": cantica_user_id, "key_id": key_id}


@router.post("/assert", response_model=AssertResponse)
def assert_auth(body: AssertRequest, store: StoreDep) -> AssertResponse:
    """Exchange a key-signed assertion for a short-lived session JWT."""
    # Standard library imports:
    import json as _json  # noqa: PLC0415

    # Third party imports:
    import jwt as pyjwt  # noqa: PLC0415

    # Local imports:
    from cantica.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=400, detail="Assertions not available when auth is disabled"
        )

    try:
        unverified = pyjwt.decode(body.assertion, options={"verify_signature": False})
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)
    cantica_user_id = unverified.get("sub") or unverified.get("iss") or ""

    key = store.get_active_jwt_key(cantica_user_id)
    if key is None:
        audit_log.warning("assert denied: no enrolled key for %r", cantica_user_id)
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)

    try:
        payload = verify_assertion(
            body.assertion,
            key.public_key,
            max_age_seconds=settings.assertion_max_age_seconds,
        )
        if not store.burn_jti(
            payload["jti"],
            "auth",
            datetime.now(UTC) + timedelta(seconds=settings.assertion_max_age_seconds),
        ):
            raise KeyAssertionError("jti replayed (auth)")
    except KeyAssertionError as exc:
        audit_log.warning("assert denied [%s]: %s", cantica_user_id, exc)
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)

    row = store.get_user_by_id(key.user_id)
    gate = gate_user(row, store.list_user_flags(key.user_id), context="assert")
    if not gate.allowed or row is None:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAILURE)

    store.touch_jwt_key(key.id)
    roles = [Role(r) for r in _json.loads(row.roles_json)]
    user = User(id=row.id, username=row.username, email=row.email, roles=roles, is_active=True)
    token = create_jwt(user, get_jwt_secret(), expire_minutes=settings.jwt_expire_minutes)
    audit_log.info(
        "assert ok: user=%s cantica_user_id=%s warnings=%s", row.id, cantica_user_id, gate.warnings
    )
    return AssertResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        warnings=gate.warnings,
    )
