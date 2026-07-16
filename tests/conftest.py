"""Session-wide test configuration.

The security shim is ON by default in production (CANTICA_SECURITY_SHIM=true),
served by the shared cantica-secure package. The in-repo security
implementation remains the fall-back path, so the existing in-repo suites pin
the flag OFF here to keep exercising it; tests/api/test_security_shim.py opts
back in explicitly (Settings(security_shim=True)). Set CANTICA_SECURITY_SHIM
in the environment to override.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import os

os.environ.setdefault("CANTICA_SECURITY_SHIM", "false")
