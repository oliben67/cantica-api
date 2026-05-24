"""
FastAPI endpoint for rendering a prompt with variable substitution.

Tag: ``render``

Endpoint
--------
``POST /v1/render``
    Resolve a prompt slug to a specific version, then render its content by
    substituting ``{{variable}}`` placeholders.  Body: ``RenderRequest``
    (``slug``, optional ``ref`` defaulting to ``"latest"``, optional
    ``variables`` dict).

    Rendering uses ``TemplateEngine.render_with_defaults``: schema-declared
    defaults are applied first, then caller-supplied ``variables`` override
    them.  Unresolvable placeholders (no default and no caller value) raise
    HTTP 422.

    Returns ``RenderResponse`` containing the rendered ``content``, the
    original ``slug``, ``ref``, and the resolved ``sha``.

    Returns HTTP 404 if the slug or ref does not exist, HTTP 422 for invalid
    slug format (must be ``"namespace/name"``) or unresolvable variables.

The module-level ``_engine = TemplateEngine()`` instance is reused across
requests.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.render import RenderRequest, RenderResponse
from cantica.services.template_engine import TemplateEngine

router = APIRouter(tags=["render"])
_engine = TemplateEngine()


@router.post("/render", response_model=RenderResponse)
def render_prompt(
    body: RenderRequest,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> RenderResponse:
    """Render a prompt version, substituting the supplied variable values."""
    namespace, name = _parse_slug(body.slug)
    try:
        store.check_namespace_access(namespace, cert_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        version = store.resolve(namespace, name, body.ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        content = _engine.render_with_defaults(version.content, version.variables, body.variables)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RenderResponse(
        content=content,
        slug=body.slug,
        ref=body.ref,
        sha=version.sha,
    )


def _parse_slug(slug: str) -> tuple[str, str]:
    """Split a ``namespace/name`` slug into its two components."""
    parts = slug.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="slug must be namespace/name")
    return parts[0], parts[1]
