# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.hooks import WebhookCreate, WebhookResponse

router = APIRouter(prefix="/hooks", tags=["hooks"])


def _fmt(hook) -> WebhookResponse:  # type: ignore[no-untyped-def]
    return WebhookResponse(
        id=hook.id,
        url=hook.url,
        events=hook.events,
        namespace=hook.namespace,
        created_at=hook.created_at.isoformat(),
    )


@router.post("", response_model=WebhookResponse, status_code=201)
def create_hook(body: WebhookCreate, store: StoreDep, _user: UserDep) -> WebhookResponse:
    hook = store.create_webhook(
        url=body.url,
        secret=body.secret,
        events=body.events,
        namespace=body.namespace,
    )
    return _fmt(hook)


@router.get("", response_model=list[WebhookResponse])
def list_hooks(store: StoreDep, _user: UserDep) -> list[WebhookResponse]:
    return [_fmt(h) for h in store.list_webhooks()]


@router.delete("/{hook_id}", status_code=204)
def delete_hook(hook_id: str, store: StoreDep, _user: UserDep) -> None:
    if not store.delete_webhook(hook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
