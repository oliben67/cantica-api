"""
Pydantic schemas for namespace and namespace certificate endpoints.

Namespace schemas
-----------------
``NamespaceCreate``   — body for ``POST /v1/namespaces``; sets visibility and
                        encoding at creation time.
``NamespaceUpdate``   — body for ``PATCH /v1/namespaces/{name}``; allows the
                        certificate holder to publish a proprietary namespace.
``NamespaceResponse`` — full namespace record returned by all namespace endpoints.

Certificate schemas
-------------------
``CertificateIssue``    — body for ``POST /v1/namespaces/{name}/certificates``;
                          specifies who the certificate is granted to and an optional
                          expiry datetime.
``CertificateResponse`` — returned at issuance (includes one-time ``token``) and
                          by list/revoke endpoints (``token`` is ``None``).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from datetime import datetime

# Third party imports:
from pydantic import BaseModel


class NamespaceCreate(BaseModel):
    """Request body for creating a new namespace."""

    name: str
    description: str = ""
    is_proprietary: bool = False
    encoded: bool = False


class NamespaceUpdate(BaseModel):
    """Request body for partially updating a namespace's metadata."""

    description: str | None = None
    is_proprietary: bool | None = None


class NamespaceResponse(BaseModel):
    """Namespace record returned by all namespace endpoints."""

    name: str
    description: str
    is_proprietary: bool
    encoded: bool
    created_at: datetime


class CertificateIssue(BaseModel):
    """Request body for issuing a namespace access certificate."""

    granted_to: str
    expires_at: datetime | None = None


class CertificateResponse(BaseModel):
    """Certificate record; includes the one-time token only at issuance."""

    id: str
    namespace: str
    granted_to: str
    issued_at: datetime
    expires_at: datetime | None
    revoked: bool
    # Only populated at issuance; None in list/revoke responses.
    token: str | None = None
