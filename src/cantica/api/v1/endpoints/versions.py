"""
FastAPI endpoints for prompt version management.

Router prefix: ``/v1/prompts``   Tag: ``versions``

Endpoints
---------
``GET  /v1/prompts/{namespace}/{name}/versions``
    Return the commit log for a branch (default: ``main``), newest first.

``POST /v1/prompts/{namespace}/{name}/versions``
    Commit new content.  Body: ``VersionCreate``.

    Normal commit: omit ``sha`` and ``created_at`` — the server computes them.

    Import (push/pull sync): supply ``sha``, ``parent_sha``, and ``created_at``
    to preserve the exact SHA across instances.  The server calls
    ``store.import_version()``, which verifies the supplied SHA matches the
    computed one and is idempotent on duplicates.  Returns HTTP 409 if the SHA
    conflicts.

``GET  /v1/prompts/{namespace}/{name}/versions/{ref}``
    Resolve a ref to a version and return it.  ``ref`` can be a branch name,
    tag name, full SHA, 7-character SHA prefix, or ``"latest"``.
    Returns HTTP 404 if the ref does not resolve.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.versions import VersionCreate, VersionResponse

router = APIRouter(prefix="/prompts", tags=["versions"])


def _to_response(version) -> VersionResponse:
    """Convert a ``Version`` domain object to its API response schema."""
    return VersionResponse(**version.model_dump())


@router.get("/{namespace}/{name}/versions", response_model=list[VersionResponse])
def list_versions(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
    branch: str = "main",
) -> list[VersionResponse]:
    """List versions of a prompt on the given branch, newest first."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [_to_response(v) for v in store.log(prompt.id, branch)]


@router.post("/{namespace}/{name}/versions", response_model=VersionResponse, status_code=201)
def commit_version(
    namespace: str,
    name: str,
    body: VersionCreate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> VersionResponse:
    """Commit a new version to the prompt, or import an existing commit verbatim."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if body.sha and body.created_at:
        try:
            version = store.import_version(
                prompt.id,
                body.sha,
                body.content,
                body.message,
                body.author,
                body.branch,
                body.parent_sha,
                body.created_at,
                body.variables,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        version = store.commit(
            prompt.id,
            body.content,
            body.message,
            body.author,
            branch=body.branch,
            variables=body.variables,
        )
    return _to_response(version)


@router.get("/{namespace}/{name}/versions/{ref}", response_model=VersionResponse)
def get_version_at_ref(
    namespace: str,
    name: str,
    ref: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> VersionResponse:
    """Resolve a ref (SHA, tag, or branch) and return the matching version."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        version = store.resolve(namespace, name, ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(version)
