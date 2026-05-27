"""
Federation permission policy loader and checker.

Config file example (``/etc/cantica/federation-policy.yaml``):

.. code-block:: yaml

    federation:
      # Default permissions for ANY federated server (no specific rule)
      default:
        - read:public

      # Per-federation overrides (apply to ALL members of a federation)
      federations:
        - id: "fed-uuid-123"
          name: acme-corp            # informational only
          allow:
            - read:public
            - read:unlisted

      # Per-member overrides (most specific; matched by RSA public-key fingerprint)
      members:
        - fingerprint: "sha256:abcdef..."
          allow:
            - read:all
            - write:prompts

Available permission strings
----------------------------
``read:public``     read public prompts (default for all)
``read:unlisted``   read unlisted prompts
``read:all``        read all prompts (public + unlisted + private)
``write:prompts``   push / create prompts
``write:namespaces`` create namespaces
``admin``           no federation member ever gets this
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import hashlib
from pathlib import Path
from typing import Any

# Third party imports:
import yaml
from pydantic import BaseModel, Field


class FederationRuleEntry(BaseModel):
    """A permission rule for a specific federation or member."""

    id: str | None = None           # federation UUID (for federation-level rules)
    name: str | None = None         # informational
    fingerprint: str | None = None  # sha256:<hex> public-key fingerprint (member rules)
    allow: list[str] = Field(default_factory=list)


class FederationPolicyConfig(BaseModel):
    """Top-level federation policy settings."""

    default: list[str] = Field(default_factory=lambda: ["read:public"])
    federations: list[FederationRuleEntry] = Field(default_factory=list)
    members: list[FederationRuleEntry] = Field(default_factory=list)


class FederationPolicy(BaseModel):
    """Loaded federation policy."""

    federation: FederationPolicyConfig = Field(default_factory=FederationPolicyConfig)

    @classmethod
    def from_yaml(cls, path: Path | str | None) -> FederationPolicy:
        """Load from *path*, or return defaults if absent."""
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            return cls()
        raw: dict[str, Any] = yaml.safe_load(p.read_text()) or {}
        return cls.model_validate(raw)

    def allowed_for(
        self,
        public_key_pem: str,
        federation_id: str | None = None,
    ) -> set[str]:
        """Return the set of permissions for a federated caller.

        Resolution order (most specific wins; all matching rules are merged):
        1. Default permissions
        2. Federation-level rule (if *federation_id* matches)
        3. Member-level rule (if RSA key fingerprint matches)
        """
        perms: set[str] = set(self.federation.default)
        fingerprint = _key_fingerprint(public_key_pem)

        if federation_id:
            for rule in self.federation.federations:
                if rule.id == federation_id:
                    perms.update(rule.allow)

        for rule in self.federation.members:
            if rule.fingerprint and rule.fingerprint == fingerprint:
                perms.update(rule.allow)

        return perms

    def can(
        self,
        permission: str,
        public_key_pem: str,
        federation_id: str | None = None,
    ) -> bool:
        """Return True if the caller holds *permission*."""
        return permission in self.allowed_for(public_key_pem, federation_id)


def _key_fingerprint(public_key_pem: str) -> str:
    """Return ``sha256:<hex>`` fingerprint of a PEM public key."""
    raw = public_key_pem.encode()
    digest = hashlib.sha256(raw).hexdigest()
    return f"sha256:{digest}"
