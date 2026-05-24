"""
FastAPI endpoints for outgoing webhook management.

Router prefix: ``/v1/hooks``   Tag: ``hooks``

Webhooks allow external systems to subscribe to Cantica events.  On each
``version.created`` event (or any other registered event), ``VersionStore``
POSTs a signed JSON payload to every matching webhook URL.  Delivery is
best-effort: failures are logged as warnings and do not affect the triggering
operation.

Payload signing: ``X-Cantica-Signature: sha256=<hmac>`` using the webhook's
``secret`` field.

Endpoints
---------
``POST   /v1/hooks``
    Register a new webhook.  Body: ``WebhookCreate`` (``url``, ``secret``,
    ``events`` list, optional ``namespace`` filter).  Returns HTTP 201.

``GET    /v1/hooks``
    List all registered webhooks.  The ``secret`` field is not included in
    list responses (``WebhookResponse`` omits it).

``DELETE /v1/hooks/{hook_id}``
    Delete a webhook by UUID.  Returns HTTP 404 if not found, HTTP 204 on
    success.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import StoreDep, UserDep
from cantica.schemas.hooks import WebhookCreate, WebhookResponse

router = APIRouter(prefix="/hooks", tags=["hooks"])


def _fmt(hook) -> WebhookResponse:  # type: ignore[no-untyped-def]
    """Convert a ``Webhook`` domain object to its API response schema."""
    return WebhookResponse(
        id=hook.id,
        url=hook.url,
        events=hook.events,
        namespace=hook.namespace,
        created_at=hook.created_at.isoformat(),
    )


@router.post("", response_model=WebhookResponse, status_code=201)
def create_hook(body: WebhookCreate, store: StoreDep, _user: UserDep) -> WebhookResponse:
    """Register a new webhook endpoint."""
    hook = store.create_webhook(
        url=body.url,
        secret=body.secret,
        events=body.events,
        namespace=body.namespace,
    )
    return _fmt(hook)


@router.get("", response_model=list[WebhookResponse])
def list_hooks(store: StoreDep, _user: UserDep) -> list[WebhookResponse]:
    """List all registered webhooks."""
    return [_fmt(h) for h in store.list_webhooks()]


@router.delete("/{hook_id}", status_code=204)
def delete_hook(hook_id: str, store: StoreDep, _user: UserDep) -> None:
    """Delete a webhook by its ID."""
    if not store.delete_webhook(hook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
