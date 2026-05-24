"""
Core utilities package.

Re-exports the public surface of the three core modules:

- ``parse_address`` / ``PromptAddress`` — address parser (``resolver.py``)
- ``security``    — API key generation and hashing (not re-exported; import directly)
- ``logger``      — logging setup (not re-exported; import directly)
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

from .resolver import PromptAddress, parse_address

__all__ = ["PromptAddress", "parse_address"]
