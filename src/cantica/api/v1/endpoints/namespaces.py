"""
FastAPI endpoints for namespace management and certificate issuance.

Router prefix: ``/v1/namespaces``   Tag: ``namespaces``

Namespace endpoints
-------------------
``GET    /v1/namespaces``
    List all namespaces visible to the caller.

``POST   /v1/namespaces``
    Create a new namespace.  Body: ``NamespaceCreate``.  ``is_proprietary``
    marks the namespace as certificate-gated; ``encoded`` enables AES-256-GCM
    encryption for all documents stored in it.

``GET    /v1/namespaces/{name}``
    Retrieve a single namespace.  Returns HTTP 404 if not found.

``PATCH  /v1/namespaces/{name}``
    Update mutable namespace fields.  To publish a proprietary namespace
    (set ``is_proprietary=false``), a valid ``X-Cantica-Certificate`` header
    is required so that only the current certificate holder can make it public.

Certificate endpoints
---------------------
``POST   /v1/namespaces/{name}/certificates``
    Issue a new certificate granting access to a proprietary namespace.
    The namespace must be proprietary.  Body: ``CertificateIssue``.  The
    ``token`` field in the response is only populated at issuance — it is
    never retrievable again.

``GET    /v1/namespaces/{name}/certificates``
    List all certificates issued for a namespace (``token`` is always
    ``None`` in list responses).

``DELETE /v1/namespaces/{name}/certificates/{cert_id}``
    Revoke a certificate.  Returns HTTP 404 if not found, HTTP 204 on success.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from fastapi import APIRouter, HTTPException

# Local imports:
from cantica.api.deps import CertTokenDep, StoreDep, UserDep
from cantica.schemas.namespaces import (
    CertificateIssue,
    CertificateResponse,
    NamespaceCreate,
    NamespaceResponse,
    NamespaceUpdate,
)

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


def _ns_to_response(ns) -> NamespaceResponse:
    """Convert a ``Namespace`` domain object to its API response schema."""
    return NamespaceResponse(
        name=ns.name,
        description=ns.description,
        is_proprietary=ns.is_proprietary,
        encoded=ns.encoded,
        created_at=ns.created_at,
    )


def _cert_to_response(cert, *, include_token: bool = False) -> CertificateResponse:
    """Convert a certificate domain object to its API response schema."""
    return CertificateResponse(
        id=cert.id,
        namespace=cert.namespace,
        granted_to=cert.granted_to,
        issued_at=cert.issued_at,
        expires_at=cert.expires_at,
        revoked=cert.revoked,
        token=cert.token if include_token else None,
    )


@router.get("", response_model=list[NamespaceResponse])
def list_namespaces(store: StoreDep, _user: UserDep) -> list[NamespaceResponse]:
    """List all namespaces."""
    return [_ns_to_response(ns) for ns in store.list_namespaces()]


@router.post("", response_model=NamespaceResponse, status_code=201)
def create_namespace(body: NamespaceCreate, store: StoreDep, _user: UserDep) -> NamespaceResponse:
    """Create a new namespace."""
    ns = store.create_namespace(
        body.name,
        body.description,
        is_proprietary=body.is_proprietary,
        encoded=body.encoded,
    )
    return _ns_to_response(ns)


@router.get("/{name}", response_model=NamespaceResponse)
def get_namespace(name: str, store: StoreDep, _user: UserDep) -> NamespaceResponse:
    """Return a single namespace by name."""
    ns = store.get_namespace(name)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return _ns_to_response(ns)


@router.patch("/{name}", response_model=NamespaceResponse)
def update_namespace(
    name: str,
    body: NamespaceUpdate,
    store: StoreDep,
    _user: UserDep,
    cert_token: CertTokenDep = None,
) -> NamespaceResponse:
    """Partially update a namespace's metadata."""
    ns = store.get_namespace(name)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")

    # Publishing a proprietary namespace requires presenting a valid certificate.
    if body.is_proprietary is False and ns.is_proprietary:
        try:
            store.check_namespace_access(name, cert_token)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        updated = store.update_namespace(
            name,
            description=body.description,
            is_proprietary=body.is_proprietary,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Namespace not found") from exc
    return _ns_to_response(updated)


@router.post("/{name}/certificates", response_model=CertificateResponse, status_code=201)
def issue_certificate(
    name: str,
    body: CertificateIssue,
    store: StoreDep,
    _user: UserDep,
) -> CertificateResponse:
    """Issue an access certificate for a proprietary namespace."""
    try:
        cert = store.issue_certificate(name, body.granted_to, expires_at=body.expires_at)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Namespace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _cert_to_response(cert, include_token=True)


@router.get("/{name}/certificates", response_model=list[CertificateResponse])
def list_certificates(
    name: str,
    store: StoreDep,
    _user: UserDep,
) -> list[CertificateResponse]:
    """List all certificates issued for a namespace."""
    ns = store.get_namespace(name)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return [_cert_to_response(c) for c in store.list_certificates(name)]


@router.delete("/{name}/certificates/{cert_id}", status_code=204)
def revoke_certificate(
    name: str,
    cert_id: str,
    store: StoreDep,
    _user: UserDep,
) -> None:
    """Revoke a namespace access certificate."""
    ns = store.get_namespace(name)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    if not store.revoke_certificate(cert_id):
        raise HTTPException(status_code=404, detail="Certificate not found")
