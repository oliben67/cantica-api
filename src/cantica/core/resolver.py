# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptAddress:
    namespace: str
    name: str
    ref: str = "latest"
    host: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.namespace}/{self.name}"

    def __str__(self) -> str:
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
