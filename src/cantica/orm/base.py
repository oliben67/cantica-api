"""
SQLAlchemy declarative base for all ORM-mapped tables.

``Base`` is the single ``DeclarativeBase`` subclass shared by every table class
in ``cantica.orm.tables``.  It drives ``Base.metadata.create_all()`` (called
by ``open_session``) and the Atlas DDL provider (``tools/atlas_loader.py``).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by all ORM table classes."""

    pass
