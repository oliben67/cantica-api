"""
Prompt address parser: ``namespace/name[@ref]`` and ``cantica://`` URI support.

``parse_address(address)`` is the single entry point.  It normalises every
address form used by the CLI and API into a ``PromptAddress`` dataclass.

Accepted forms
--------------
``namespace/name``
    Bare slug; ref defaults to ``"latest"``.

``namespace/name@ref``
    Slug with an explicit ref (SHA prefix, tag name, or branch name).

``cantica://namespace/name``
    Absolute URI without a ref; ref defaults to ``"latest"``.

``cantica://namespace/name@ref``
    Absolute URI with an explicit ref.

``cantica://host/namespace/name@ref``
    Remote URI.  The ``host`` component is preserved in ``PromptAddress.host``
    so ``VersionStore.resolve_uri`` can choose between local and remote
    resolution.

``PromptAddress`` is a frozen dataclass with four fields:
- ``namespace`` — user or organisation name
- ``name``      — prompt name within the namespace
- ``ref``       — version ref string (default ``"latest"``)
- ``host``      — remote hostname (``None`` for local addresses)

The ``slug`` property returns ``"namespace/name"`` and ``__str__`` produces
the full canonical ``cantica://`` URI.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptAddress:
    """Parsed representation of a cantica:// or ``namespace/name[@ref]`` address."""

    namespace: str
    name: str
    ref: str = "latest"
    host: str | None = None

    @property
    def slug(self) -> str:
        """Return the ``namespace/name`` slug."""
        return f"{self.namespace}/{self.name}"

    def __str__(self) -> str:
        """Return the canonical ``cantica://`` URI string."""
        host_part = f"{self.host}/" if self.host else ""
        return f"cantica://{host_part}{self.namespace}/{self.name}@{self.ref}"


def parse_address(address: str) -> PromptAddress:
    """
    Parse a prompt address string into a PromptAddress.

    Accepted forms:
        namespace/name
        namespace/name@ref
        cantica://namespace/name
        cantica://namespace/name@ref
        cantica://host/namespace/name@ref
    """
    original = address
    host: str | None = None

    if address.startswith("cantica://"):
        address = address[len("cantica://") :]
        parts = address.split("/")
        if len(parts) == 2:
            namespace_part, name_ref = parts
        elif len(parts) == 3:
            host, namespace_part, name_ref = parts
        else:
            raise ValueError(f"invalid cantica address: {original!r}")
    else:
        parts = address.split("/")
        if len(parts) != 2:
            raise ValueError(f"invalid address {original!r} — expected namespace/name[@ref]")
        namespace_part, name_ref = parts

    name, ref = name_ref.rsplit("@", 1) if "@" in name_ref else (name_ref, "latest")

    if not namespace_part or not name or not ref:
        raise ValueError(f"invalid address: {original!r}")

    return PromptAddress(namespace=namespace_part, name=name, ref=ref, host=host)
