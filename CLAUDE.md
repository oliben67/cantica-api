# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All common tasks are in `Taskfile.yml` and run via `task`. Run `task` alone to list them.

```bash
task test              # full suite with coverage (≥ 99% required)
task test:fast         # no coverage, fast iteration
task test:one -- <pat> # run tests matching a name pattern (e.g. task test:one -- branch)
task test:file -- <f>  # run a single file (e.g. task test:file -- tests/test_cli.py)
task check             # lint + format check + typecheck + test (full CI gate)
task fix               # auto-fix lint issues and reformat
task lint              # ruff check only
task format            # ruff format only
task typecheck         # mypy on src/cantica/
task serve             # dev server at http://localhost:8042 (auto-reload)
```

**Migrations (Atlas, not Alembic):**
```bash
task db:new -- <name>  # plan migration from ORM changes
task db:validate       # verify atlas.sum integrity
```
After changing any `orm/tables.py` class, run `task db:new` to generate a migration. `tools/atlas_loader.py` is the bridge that prints DDL from SQLAlchemy models for Atlas to diff.

## Architecture

### Layer model

```
Pydantic models (models/)
        ↓
SQLAlchemy ORM (orm/tables.py)  ←→  BlobStore (objects/ dir)
        ↓
VersionStore (services/version_store.py)   ← the single core service
        ↓
FastAPI endpoints (api/v1/endpoints/)  +  Typer CLI (cli.py)
```

**VersionStore** is the authoritative interface for all data operations. Both the API layer (`api/deps.py`) and CLI (`cli.py`) talk exclusively through it. Endpoints never touch the ORM directly.

### Storage split: metadata vs content

Prompt *metadata* (name, tags, variables, etc.) lives in SQLite. Prompt *content* is stored separately in a git-style content-addressable blob store (`BlobStore`): files under `<vault>/objects/<2-char prefix>/<remaining SHA256>`. A `VersionOrm.content_sha` column links the two. This means content is deduplicated by hash and never stored in the DB.

### Date/JSON encoding

All datetimes are stored as ISO 8601 strings in varchar columns (no native datetime type). JSON arrays (`tags`, `model_hints`, `variables`) are also stored as serialised strings. Conversion helpers `_iso()` / `_from_iso()` and `json.dumps` / `json.loads` are used inline in `VersionStore`.

### Commit SHA

A version's SHA is not a content hash — it is `sha256("commit\n<content_sha>\n<parent_sha>\n<author>\n<message>\n<created_at_iso>")`, matching a git-style commit object. This makes SHAs unique per commit even for identical content.

### FastAPI wiring

- `api/deps.py` exposes three `Annotated` aliases used in endpoint signatures: `StoreDep`, `UserDep`, `SettingsDep`.
- `get_store()` is `@lru_cache`-wrapped (one `VersionStore` per process). In tests it is replaced via `app.dependency_overrides[get_store] = lambda: test_store`.
- Auth is opt-in (`CANTICA_AUTH_ENABLED=true`). When disabled every request gets `{"id": "local", "name": "local"}`.

### VersionStore lifecycle

`VersionStore` holds an engine and a session. Always call `store.close()` when done — this disposes the connection pool and avoids `ResourceWarning: unclosed database`. In test fixtures use `yield store` + `store.close()` teardown, not `return`.

### Adding a new endpoint

1. Add Pydantic request/response schemas to `schemas/`.
2. Add service methods to `VersionStore` in `services/version_store.py`.
3. Create or extend an endpoint module in `api/v1/endpoints/`.
4. Register the router in `api/v1/router.py`.
5. If new ORM columns are needed, update `orm/tables.py` then `task db:new`.

### Code style enforced by ruff

- `from __future__ import annotations` is **required** at the top of every file (ruff auto-inserts it via `isort.required-imports`).
- Import sections are ordered: future → stdlib → third-party → first-party → local-folder, each with a comment header.

### Configuration

All settings are in `config.py` (`pydantic-settings`), env prefix `CANTICA_`. Key vars: `CANTICA_VAULT_PATH`, `CANTICA_AUTH_ENABLED`, `CANTICA_PORT`, `CANTICA_REMOTE_URL`.
