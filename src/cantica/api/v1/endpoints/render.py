# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.render import RenderRequest, RenderResponse
from cantica.services.template_engine import TemplateEngine

router = APIRouter(tags=["render"])
_engine = TemplateEngine()


@router.post("/render", response_model=RenderResponse)
def render_prompt(
    body: RenderRequest,
    store: StoreDep,
    _user: UserDep,
) -> RenderResponse:
    namespace, name = _parse_slug(body.slug)
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
    parts = slug.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="slug must be namespace/name")
    return parts[0], parts[1]
