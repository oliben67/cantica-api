"""
PyPI-style multipart prompt upload endpoint.

Router prefix: ``/v1/upload``   Tag: ``upload``

Endpoint
--------
``POST /v1/upload``
    Upload a prompt version via multipart form data.  This mirrors the PyPI
    legacy upload API shape so that CLI tools and web forms can use the same
    endpoint.

    Required fields:
        ``namespace``   Namespace name (auto-created if absent).
        ``name``        Prompt name (auto-created if absent).
        ``content``     Prompt content (plain text or file upload).

    Optional fields:
        ``message``     Commit message (default: "Uploaded via web").
        ``branch``      Target branch (default: "main").
        ``description`` Prompt description (only applied on creation).
        ``tags``        Comma-separated tag list.

Returns the created ``Version`` as JSON.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

# Local imports:
from cantica.api.deps import StoreDep, WriteUserDep
from cantica.schemas.versions import VersionResponse

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=VersionResponse, status_code=201)
async def upload_prompt(
    store: StoreDep,
    user: WriteUserDep,
    namespace: str = Form(...),
    name: str = Form(...),
    content: str | None = Form(default=None),
    content_file: UploadFile | None = None,
    message: str = Form(default="Uploaded via web"),
    branch: str = Form(default="main"),
    description: str = Form(default=""),
    tags: str = Form(default=""),
) -> JSONResponse:
    """Upload a prompt version; create the prompt if it does not exist."""
    # Resolve content from form field or file upload
    resolved_content: str
    if content_file is not None:
        raw = await content_file.read()
        resolved_content = raw.decode("utf-8", errors="replace")
    elif content is not None:
        resolved_content = content
    else:
        raise HTTPException(
            status_code=422, detail="Either 'content' or 'content_file' is required"
        )

    # Auto-create namespace and prompt if missing
    if store.get_namespace(namespace) is None:
        store.create_namespace(namespace)
    prompt = store.get_prompt(namespace, name)
    if prompt is None:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        prompt = store.create_prompt(namespace, name, description, tags=tag_list)

    version = store.commit(prompt.id, resolved_content, message, user.username, branch=branch)
    return JSONResponse(
        status_code=201,
        content={
            "sha": version.sha,
            "prompt_id": version.prompt_id,
            "branch": version.branch,
            "message": version.message,
            "author": version.author,
            "created_at": version.created_at.isoformat(),
        },
    )
