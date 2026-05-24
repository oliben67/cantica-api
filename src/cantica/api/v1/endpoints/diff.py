"""
FastAPI endpoint for unified text diff between two prompt versions.

Router prefix: ``/v1/prompts``   Tag: ``diff``

Endpoint
--------
``POST /v1/prompts/{namespace}/{name}/diff``
    Compute a unified diff between two refs.  Body: ``DiffRequest``
    (``ref1``, ``ref2``).  Both refs are resolved through the full ref
    resolution chain (branch, tag, SHA prefix, etc.) before diffing.

    Returns ``DiffResponse`` containing:
    - ``diff``      — unified diff string (empty string if content is identical)
    - ``ref1/ref2`` — the original ref strings as supplied
    - ``namespace`` — echoed from the URL path
    - ``name``      — echoed from the URL path

    Returns HTTP 404 if the prompt or either ref does not resolve.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.diff import DiffRequest, DiffResponse

router = APIRouter(prefix="/prompts", tags=["diff"])


@router.post("/{namespace}/{name}/diff", response_model=DiffResponse)
def diff_versions(
    namespace: str,
    name: str,
    body: DiffRequest,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> DiffResponse:
    """Return a unified-diff between two refs of a prompt."""
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    prompt = store.get_prompt(namespace, name)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    try:
        v1 = store.resolve(namespace, name, body.ref1)
        v2 = store.resolve(namespace, name, body.ref2)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DiffResponse(
        diff=store.diff(v1.sha, v2.sha),
        ref1=body.ref1,
        ref2=body.ref2,
        namespace=namespace,
        name=name,
    )
