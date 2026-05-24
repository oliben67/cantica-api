"""
Logging configuration for the Cantica server and CLI.

``setup_logging(level)`` configures the root logger with a timestamped
format and suppresses noisy Uvicorn access logs.  It is called once by
``create_app()`` (FastAPI) at startup.

``get_logger(name)`` is a thin wrapper around ``logging.getLogger`` provided
for consistency; modules import it instead of using the standard library
directly.

Log format:  ``YYYY-MM-DDTHH:MM:SS  LEVEL     name  message``

Third-party suppressions:
- ``uvicorn.access`` → WARNING (avoids a log line per HTTP request in dev).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import logging
import sys


def setup_logging(level: str = "info") -> None:
    """Configure the root logger with a structured format and quiet noisy dependencies."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )
    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named ``logging.Logger`` instance."""
    return logging.getLogger(name)
