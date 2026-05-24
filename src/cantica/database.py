"""
Database engine factory with full-text search (FTS) initialisation.

``open_session(url_or_path, *, create_tables)`` is the single entry point for
obtaining a configured SQLAlchemy engine and session.  It:

1. Accepts either a filesystem ``Path`` (auto-expanded to ``sqlite:///<path>``)
   or a full SQLAlchemy URL string (SQLite or PostgreSQL).
2. Creates all ORM-mapped tables (``Base.metadata.create_all``) unless
   ``create_tables=False``.
3. Sets up full-text search in a backend-specific way:
   - **SQLite**: creates an FTS5 virtual table ``prompts_fts`` covering
     ``name``, ``description``, and a ``body`` column that concatenates tags
     and model hints.  WAL journal mode and ``PRAGMA foreign_keys = ON`` are
     also enabled on every new connection via a SQLAlchemy ``connect`` event.
   - **PostgreSQL**: adds a ``search_vector tsvector`` column on the
     ``prompts`` table, a GIN index over it, and a ``BEFORE INSERT OR UPDATE``
     trigger (``trg_prompts_tsv``) that auto-populates the vector from
     ``name``, ``description``, ``tags``, and ``model_hints``.
4. Returns ``(engine, Session)`` where the session has ``autoflush=False``
   so callers control when flushes happen.

Both the CLI (``VersionStore.__init__``) and the API server call this function
indirectly through ``VersionStore``.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

# Local imports:
from cantica.core.certificates import generate_instance_secret
from cantica.orm.base import Base

# SQLite FTS5 virtual table (SQLite-only).
_FTS5_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts "
    "USING fts5(prompt_id UNINDEXED, name, description, body)"
)

# PostgreSQL: tsvector column, GIN index, and auto-update trigger.
_PG_FTS_DDL = [
    """
    ALTER TABLE prompts
      ADD COLUMN IF NOT EXISTS search_vector tsvector
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_prompts_search_vector
      ON prompts USING GIN (search_vector)
    """,
    """
    CREATE OR REPLACE FUNCTION _cantica_prompts_tsv() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      NEW.search_vector := to_tsvector('english',
        coalesce(NEW.name, '') || ' ' ||
        coalesce(NEW.description, '') || ' ' ||
        regexp_replace(NEW.tags, '[\\[\\]"]', ' ', 'g') || ' ' ||
        regexp_replace(NEW.model_hints, '[\\[\\]"]', ' ', 'g')
      );
      RETURN NEW;
    END;
    $$
    """,
    """
    DO $$ BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_prompts_tsv'
          AND tgrelid = 'prompts'::regclass
      ) THEN
        CREATE TRIGGER trg_prompts_tsv
          BEFORE INSERT OR UPDATE ON prompts
          FOR EACH ROW EXECUTE FUNCTION _cantica_prompts_tsv();
      END IF;
    END $$
    """,
]


def open_session(
    url_or_path: str | Path,
    *,
    create_tables: bool = True,
) -> tuple[Engine, Session]:
    """Open a database connection and return the engine + a ready-to-use Session.

    Accepts either:
    - a ``Path`` (SQLite file) — expanded to ``sqlite:///<path>``
    - a full SQLAlchemy URL string (``sqlite:///...`` or ``postgresql://...``)
    """
    if isinstance(url_or_path, Path):
        url = f"sqlite:///{url_or_path}"
    else:
        url = url_or_path

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args)
    dialect = engine.dialect.name

    if dialect == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            """Set essential SQLite pragmas (foreign keys, WAL mode) on each new connection."""
            dbapi_conn.execute("PRAGMA foreign_keys = ON")
            dbapi_conn.execute("PRAGMA journal_mode = WAL")

    if create_tables:
        Base.metadata.create_all(engine)

    if dialect == "sqlite":
        with engine.begin() as conn:
            conn.execute(text(_FTS5_DDL))
    elif dialect == "postgresql":  # pragma: no cover
        with engine.begin() as conn:
            for ddl in _PG_FTS_DDL:
                conn.execute(text(ddl))

    session = Session(engine, autoflush=False)
    if create_tables:
        _ensure_instance_config(session)
    return engine, session


def _ensure_instance_config(session: Session) -> None:
    """Bootstrap the instance_config row with a signing secret on first run."""
    # Local imports:
    from cantica.orm.tables import InstanceConfigOrm  # avoid circular at module load

    row = session.get(InstanceConfigOrm, "certificate_secret")
    if not row:
        session.add(
            InstanceConfigOrm(key="certificate_secret", value=generate_instance_secret())
        )
        session.commit()
