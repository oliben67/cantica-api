# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException, Query

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.comments import CommentCreate, CommentResponse

router = APIRouter(prefix="/prompts", tags=["comments"])


def _to_response(comment) -> CommentResponse:
    return CommentResponse(**comment.model_dump())


@router.post("/{namespace}/{name}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    namespace: str,
    name: str,
    body: CommentCreate,
    store: StoreDep,
    user: UserDep,
) -> CommentResponse:
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
    version_sha: str | None = Query(None, description="Filter by version SHA"),
) -> list[CommentResponse]:
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
) -> None:
    store.delete_comment(comment_id)
