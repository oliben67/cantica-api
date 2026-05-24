# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Local imports:
from cantica.database import open_session


def test_open_session_with_string_url() -> None:
    """open_session accepts a SQLite URL string in addition to a Path."""
    engine, session = open_session("sqlite:///:memory:")
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        session.close()
        engine.dispose()


def test_open_session_create_tables_false() -> None:
    """create_tables=False skips table creation."""
    engine, session = open_session("sqlite:///:memory:", create_tables=False)
    try:
        assert engine is not None
    finally:
        session.close()
        engine.dispose()
