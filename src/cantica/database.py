# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

# Local imports:
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

    return engine, Session(engine, autoflush=False)
