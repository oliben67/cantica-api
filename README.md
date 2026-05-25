# Cantica

> A git-flavored registry for AI prompts — versioned, forkable, searchable.

Like PyPI for Python packages, but for prompts:
every prompt is versioned, diffable, and addressable as `namespace/name@ref`.

---

## Quickstart (< 5 minutes)

### Prerequisites

- [uv](https://docs.astral.sh/uv/) ≥ 0.5
- Python 3.14

### Install

```bash
git clone https://github.com/osteck/cantica
cd cantica
uv sync
```

### Start the server

```bash
cantica serve --reload
# → http://localhost:8042
# → http://localhost:8042/docs  (Swagger UI)
```

Or with Docker Compose (no Python required):

```bash
docker compose up
```

---

## 5-minute tour

### 1 — Create a prompt

```bash
cantica new osteck/architect -d "A senior software architect"
```

### 2 — Commit a version

```bash
echo "You are a senior architect specialising in {{language}}." \
  | cantica commit osteck/architect -m "Initial"
```

Or from a file:

```bash
cantica commit osteck/architect -m "Initial" -f prompt.txt
```

### 3 — View history

```bash
cantica log osteck/architect
# abc1234  2026-05-23 10:00  osteck  Initial
```

### 4 — Show the latest version

```bash
cantica show osteck/architect
cantica show osteck/architect --raw   # content only
```

### 5 — Render with variables

```bash
cantica render osteck/architect --var language=Python
# You are a senior architect specialising in Python.
```

### 6 — Tag a stable release

```bash
cantica tag osteck/architect v1.0
cantica show osteck/architect@v1.0
```

### 7 — Diff two versions

```bash
cantica diff osteck/architect v1.0 latest
```

### 8 — Work on a branch

```bash
cantica branch osteck/architect experimental
cantica commit osteck/architect -m "Experiment" -b experimental -f new.txt
cantica merge osteck/architect --from experimental   # fast-forward onto main
```

### 9 — Fork a prompt

```bash
cantica fork community/architect osteck/my-architect
cantica log osteck/my-architect
```

### 10 — List and search prompts

```bash
cantica list                          # all prompts in vault
cantica list --tag python             # filter by tag
cantica list --model gpt4             # filter by model hint
cantica list --visibility public      # filter by visibility

cantica search "senior architect"                 # full-text search
cantica search "architect" --tag python           # search + tag filter
cantica search "architect" --namespace osteck     # search in namespace
```

### 11 — Push / Pull to another Cantica instance

```bash
# Push local prompt to a remote
cantica push osteck/architect --remote http://cantica.example.com

# Pull a prompt from a remote
cantica pull community/architect --remote http://cantica.example.com

# Push/pull to/from a proprietary namespace (requires a certificate token)
cantica push myorg/secret-prompt --remote http://cantica.example.com --certificate <token>
cantica pull myorg/secret-prompt --remote http://cantica.example.com --certificate <token>
```

### 12 — Namespace access control

```bash
# Create a proprietary namespace — prompts require a certificate to access
cantica namespace-new myorg --proprietary

# Create an encoded namespace — content is encrypted at rest (AES-256-GCM)
cantica namespace-new private-vault --encoded

# List all namespaces
cantica namespace-list

# Issue an access certificate for a collaborator
cantica cert-issue myorg --to alice
# Prints the one-time token — save it immediately:
#   ID:    c1d2e3f4-...
#   Token: eyJuYW1lc3BhY2UiOiJteW9yZyJ9.abc123...

# List certificates for a namespace
cantica cert-list myorg

# Revoke a certificate
cantica cert-revoke c1d2e3f4-...

# Use a certificate when accessing prompts on a proprietary remote
cantica push myorg/secret --remote http://cantica.example.com --certificate <token>
cantica pull myorg/secret --remote http://cantica.example.com --certificate <token>
```

---

## Core concepts

| Concept | One-line summary |
|---|---|
| **Namespace** | Owner-level scope (`osteck`, `my-org`). Can be *proprietary* (certificate-gated) or *encoded* (AES-256-GCM at rest). |
| **Prompt** | The primary object — metadata + full version history, identified by `namespace/name`. |
| **Version** | An immutable commit. SHA computed from content, parent SHA, author, message, and timestamp — exactly like git. |
| **Branch** | A named, mutable pointer to a version HEAD. Every prompt starts with `main`. Supports create, merge (fast-forward), and rollback. |
| **Tag** | A named, immutable pointer to a specific SHA. Use for stable releases (`v1.0`, `production`). |
| **Ref** | Anything that resolves to a version: `latest`, a tag name, a branch name, a full SHA, or a SHA prefix. |
| **Blob store** | Content-addressable filesystem store for prompt text — separate from the DB, deduplicated by SHA-256. |
| **Variable** | `{{name}}` placeholder in prompt content. Declared with a schema (required, default, description) and substituted at render time. |
| **Fork** | A deep copy of a prompt with full history, tracked lineage, and independent future commits. |
| **Collection** | A curated, mutable set of prompts — like a playlist. No version control on membership. |
| **Certificate** | HMAC-SHA256 signed token granting access to a proprietary namespace. Issued once, revocable. |
| **Visibility** | Per-prompt discovery flag: `public` · `private` · `unlisted` · `team`. |

→ **[Full concept definitions with examples → docs/concepts.md](docs/concepts.md)**

---

## Configuration

All settings are driven by environment variables (prefix `CANTICA_`):

| Variable | Default | Description |
|---|---|---|
| `CANTICA_VAULT_PATH` | `~/.cantica/vault` | Local SQLite + blob store root |
| `CANTICA_PORT` | `8042` | API server port |
| `CANTICA_HOST` | `0.0.0.0` | API server bind host |
| `CANTICA_AUTH_ENABLED` | `false` | Require `X-API-Key` header |
| `CANTICA_REMOTE_URL` | _(empty)_ | Default remote for push/pull |
| `CANTICA_LOG_LEVEL` | `info` | Log verbosity |

Create an `.env` file or export variables before running.

### Enable API key auth

```bash
export CANTICA_AUTH_ENABLED=true
cantica serve

# Create a key via the API
curl -X POST http://localhost:8042/v1/tokens \
  -H "Content-Type: application/json" \
  -d '{"name": "my-key"}'
# → {"id": "...", "name": "my-key", "raw_key": "cantica_..."}

# Use it
curl http://localhost:8042/v1/prompts \
  -H "X-API-Key: cantica_..."
```

---

## REST API

Full interactive docs at `/docs` when the server is running.

```
GET    /health

GET    /v1/namespaces                                   list namespaces
POST   /v1/namespaces                                   create namespace
GET    /v1/namespaces/{name}                            get namespace
PATCH  /v1/namespaces/{name}                            update namespace
POST   /v1/namespaces/{name}/certificates               issue access certificate
GET    /v1/namespaces/{name}/certificates               list certificates
DELETE /v1/namespaces/{name}/certificates/{id}          revoke certificate

GET    /v1/prompts                              list / search prompts
POST   /v1/prompts                              create prompt
GET    /v1/prompts/{ns}/{name}                  get prompt
DELETE /v1/prompts/{ns}/{name}                  delete prompt

GET    /v1/prompts/{ns}/{name}/versions         list versions
POST   /v1/prompts/{ns}/{name}/versions         commit new version
GET    /v1/prompts/{ns}/{name}/versions/{ref}   get at SHA / tag / branch

GET    /v1/prompts/{ns}/{name}/tags             list tags
POST   /v1/prompts/{ns}/{name}/tags             create tag
GET    /v1/prompts/{ns}/{name}/branches         list branches
POST   /v1/prompts/{ns}/{name}/branches         create branch

POST   /v1/prompts/{ns}/{name}/diff             diff two refs
POST   /v1/render                               render with variables

POST   /v1/prompts/{ns}/{name}/fork             fork into a new namespace
GET    /v1/prompts/{ns}/{name}/forks            list forks
POST   /v1/prompts/{ns}/{name}/rollback         reset branch to a past ref
POST   /v1/prompts/{ns}/{name}/merge            fast-forward merge a branch

POST   /v1/tokens                               create API token
GET    /v1/tokens                               list tokens
DELETE /v1/tokens/{id}                          revoke token
```

> **Proprietary namespaces:** all `/v1/prompts/{ns}/...` endpoints return `403 Forbidden` when the namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

## Addressing scheme

```
namespace/name                → latest on default branch
namespace/name@latest         → same
namespace/name@v1.0           → tagged release
namespace/name@abc1234        → pinned to SHA prefix
namespace/name@experimental   → named branch head

cantica://namespace/name@ref  → full URI (for songbook integration)
```

---

## Development

```bash
task install        # uv sync --all-groups
task test           # pytest with coverage
task lint           # ruff check
task format         # ruff format
task check          # lint + format check + typecheck + test
task serve          # dev server with --reload
task ui:dev         # frontend dev server at http://localhost:5173 (proxies /v1 → :8042)
task ui:build       # build frontend to frontend/dist/
task --list         # all available tasks
```

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 — Data Model | Pydantic models, VersionStore, TemplateEngine, SQLite | ✅ Done |
| 1 — Core API + CLI | FastAPI, auth, Docker, push/pull | ✅ Done |
| 2 — Full Versioning | Branches, forks, rollback, merge | ✅ Done |
| 3 — Search | Full-text (FTS5), tag/model/visibility filters | ✅ Done |
| 4 — Community | Stars, comments, collections | ✅ Done |
| 5 — Web UI | React SPA (Vite + Tailwind + shadcn/ui) | ✅ Done |
| 6 — songbook Integration | `cantica://` URI resolution, lock file | ✅ Done |
| 7 — Cloud | PostgreSQL, production Docker, federation webhooks | ✅ Done |
| 8 — Access Control | Proprietary namespaces, access certificates, AES-256-GCM encoding | ✅ Done |
