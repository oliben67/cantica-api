# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter

# Local imports:
from cantica.api.v1.endpoints import (
    auth,
    branches,
    collections,
    comments,
    diff,
    forks,
    hooks,
    prompts,
    render,
    resolve,
    stars,
    tags,
    versions,
)

router = APIRouter()

router.include_router(prompts.router)
router.include_router(versions.router)
router.include_router(tags.router)
router.include_router(branches.router)
router.include_router(forks.router)
router.include_router(stars.router)
router.include_router(comments.router)
router.include_router(collections.router)
router.include_router(diff.router)
router.include_router(render.router)
router.include_router(resolve.router)
router.include_router(hooks.router)
router.include_router(auth.router)
