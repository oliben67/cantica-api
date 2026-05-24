"""
FastAPI endpoints for prompt comments.

Router prefix: ``/v1/prompts``   Tag: ``comments``

Comments are threaded text notes attached to a prompt, optionally pinned to a
specific version SHA.  The author is taken from the authenticated user's ID
(``user["id"]``), so the caller does not supply it in the request body.

Endpoints
---------
``POST   /v1/prompts/{namespace}/{name}/comments``
    Add a comment.  Body: ``CommentCreate`` (``body``, optional
    ``version_sha``).  Returns HTTP 404 if the prompt does not exist.

``GET    /v1/prompts/{namespace}/{name}/comments``
    List all comments for a prompt.  Optional ``version_sha`` query parameter
    filters to comments pinned to a specific version.

``DELETE /v1/prompts/{namespace}/{name}/comments/{comment_id}``
    Delete a comment by UUID.  Returns HTTP 204 (no-op if the comment does not
    exist — ``store.delete_comment`` returns a bool that is not surfaced here).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.comments import CommentCreate, CommentResponse

router = APIRouter(prefix="/prompts", tags=["comments"])


def _to_response(comment) -> CommentResponse:
    """Convert a ``Comment`` domain object to its API response schema."""
    return CommentResponse(**comment.model_dump())


@router.post("/{namespace}/{name}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    namespace: str,
    name: str,
    body: CommentCreate,
    store: StoreDep,
    user: UserDep,
    cert_token: CertTokenDep = None,
) -> CommentResponse:
    """Add a comment to a prompt, optionally anchored to a specific version SHA."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        comment = store.add_comment(namespace, name, body.body, user["id"], body.version_sha)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(comment)


@router.get("/{namespace}/{name}/comments", response_model=list[CommentResponse])
def list_comments(
    namespace: str,
    name: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
    version_sha: str | None = Query(None, description="Filter by version SHA"),
) -> list[CommentResponse]:
    """List comments on a prompt, optionally filtered by version SHA."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        comments = store.list_comments(namespace, name, version_sha)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_to_response(c) for c in comments]


@router.delete("/{namespace}/{name}/comments/{comment_id}", status_code=204)
def delete_comment(
    namespace: str,
    name: str,
    comment_id: str,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> None:
    """Delete a comment by its ID."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    store.delete_comment(comment_id)
