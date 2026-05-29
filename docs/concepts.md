# Cantica — Core Concepts

> A precise reference for every first-class concept in Cantica.
> For HTTP endpoints see the [API Developer Manual](api-manual.md); for CLI usage see `cantica --help`.

---

## Table of contents

1. [Namespace](#1-namespace)
2. [Prompt](#2-prompt)
3. [Version (Commit)](#3-version-commit)
4. [Branch](#4-branch)
5. [Tag](#5-tag)
6. [Ref resolution](#6-ref-resolution)
7. [Blob store](#7-blob-store)
8. [Variables and rendering](#8-variables-and-rendering)
9. [Fork](#9-fork)
10. [Collection](#10-collection)
11. [Visibility](#11-visibility)
12. [Access control](#12-access-control)
13. [Stars and comments](#13-stars-and-comments)
14. [Webhooks](#14-webhooks)
15. [Federation — push and pull](#15-federation--push-and-pull)
16. [Addressing scheme](#16-addressing-scheme)
17. [Shim — library embedding](#17-shim--library-embedding)

---

## 1. Namespace

A **namespace** is the owner-level scope for all prompts and collections. It mirrors GitHub's `owner/repo` model. Every prompt, collection, and certificate belongs to exactly one namespace.

```
osteck/architect          ← namespace: osteck
my-org/review-team        ← namespace: my-org
community/senior-arch     ← namespace: community
```

Namespaces are created explicitly before use. The same namespace can own many prompts.

### Fields

| Field | Description |
|---|---|
| `name` | Unique identifier — the URL-safe prefix used in slugs |
| `description` | Human-readable description |
| `is_proprietary` | When `true`, all operations require a valid `X-Cantica-Certificate` header |
| `encoded` | When `true`, version content is encrypted at rest with AES-256-GCM |

### Access modes

| Mode | `is_proprietary` | `encoded` | Behaviour |
|---|---|---|---|
| Public | `false` | `false` | No certificate required; appears in search |
| Proprietary | `true` | `false` | Certificate required for every operation; excluded from search without certificate |
| Encoded | `false` | `true` | Content encrypted at rest; always excluded from search |
| Proprietary + encoded | `true` | `true` | Both restrictions apply |

### Examples

```bash
# Create a public namespace
cantica namespace-new osteck

# Create a proprietary namespace — all operations require a certificate
cantica namespace-new acme --proprietary

# Create an encoded namespace — content encrypted at rest
cantica namespace-new private-vault --encoded

# List all namespaces
cantica namespace-list
```

---

## 2. Prompt

A **prompt** is the primary registry object. It is not merely raw text — it is a structured artifact with metadata, variables, visibility, and a full version history. Think of it as a git repository whose sole tracked file is the prompt text.

A prompt is uniquely identified by its **slug**: `{namespace}/{name}`.

```
osteck/code-reviewer        ← slug
└── namespace: osteck
└── name:      code-reviewer
```

### Fields

| Field | Description |
|---|---|
| `id` | UUID — stable internal identifier |
| `namespace` | Owner namespace |
| `name` | Name, unique within the namespace |
| `slug` | Computed `namespace/name` — the canonical address |
| `description` | Short searchable description |
| `tags` | Array of searchable labels (e.g. `["python", "review"]`) |
| `model_hints` | Suggested model identifiers (e.g. `["gpt-4o", "claude-opus-4"]`) |
| `license` | SPDX identifier; defaults to `MIT` |
| `visibility` | `public` · `private` · `unlisted` · `team` (see [Visibility](#11-visibility)) |
| `variables` | Declared template variables (see [Variables and rendering](#8-variables-and-rendering)) |
| `default_branch` | Branch used when no branch is specified (default: `main`) |
| `star_count` | Cached stargazer count |
| `fork_count` | Cached fork count |

### Examples

```bash
# Create a prompt
cantica new osteck/code-reviewer -d "Reviews code for correctness and style" \
  --tag python --tag review --model gpt-4o

# View it
cantica show osteck/code-reviewer

# Delete it (removes all versions, branches, tags)
# (API only: DELETE /v1/prompts/osteck/code-reviewer)
```

---

## 3. Version (Commit)

A **version** is an immutable commit — a point-in-time snapshot of a prompt's content. Versions form a singly-linked list via `parent_sha`, giving every prompt a traversable, tamper-evident history exactly like git commits.

```
main:   [root v1] ──► [v2] ──► [v3] (HEAD)
                        │
experimental:           └──► [v4] ──► [v5] (HEAD)
```

### Fields

| Field | Description |
|---|---|
| `sha` | 64-char hex SHA-256 — the version's unique identity |
| `branch` | Branch this version was committed to |
| `parent_sha` | Previous version's SHA; `null` for the root commit |
| `message` | Commit message |
| `author` | Author identifier (usually the namespace name) |
| `content` | Full prompt text (retrieved from the blob store at read time) |
| `content_sha` | SHA-256 of the raw content — links to blob store |
| `variables` | Snapshot of the variable schema at this version |
| `created_at` | ISO 8601 UTC timestamp |
| `tags` | Tag names currently pointing to this SHA (populated at read time) |

### SHA computation

The version SHA is derived from the commit object, not from the content alone:

```
sha256(
  "commit\n"
  + content_sha + "\n"
  + (parent_sha or "") + "\n"
  + author + "\n"
  + message + "\n"
  + created_at_iso
)
```

This means two identical prompt texts committed at different times, or by different authors, will have different SHAs — just like git. It also means SHAs are verifiable: any tampering with author, message, or timestamp will produce a mismatched SHA.

### Storage split

Metadata (SHA, parent SHA, author, message, branch, timestamps, variables) lives in the database. Content itself lives in the **blob store** (see §7), referenced by `content_sha`. Multiple versions that happen to contain identical text share a single blob — deduplication is automatic.

### Examples

```bash
# Commit a new version from stdin
echo "You are a senior architect in {{language}}." \
  | cantica commit osteck/architect -m "Initial"

# Commit from a file
cantica commit osteck/architect -m "Tighten edge-case handling" -f v2.txt

# Commit to a branch other than main
cantica commit osteck/architect -m "Experiment" -b experimental -f draft.txt

# View full history
cantica log osteck/architect
# abc1234  2026-05-23 10:00  osteck  Initial
# def5678  2026-05-23 11:00  osteck  Tighten edge-case handling

# Show a specific version
cantica show osteck/architect@def5678
```

---

## 4. Branch

A **branch** is a mutable named pointer to the HEAD of a chain of versions. Branches are prompt-scoped — each prompt has its own independent set of branches.

Every prompt starts with a single branch named `main`. New branches diverge from an existing commit SHA.

```
Commit history on main:
  v1 ──► v2 ──► v3 (HEAD of main)

After branching from v2 and committing on experimental:
  v1 ──► v2 ──► v3 (HEAD of main)
          │
          └──► v4 ──► v5 (HEAD of experimental)

After merging experimental into main:
  v1 ──► v2 ──► v3 ──► v6 (HEAD of main, content = v5)
          │
          └──► v4 ──► v5 (HEAD of experimental, unchanged)
```

### Fields

| Field | Description |
|---|---|
| `name` | Branch name, unique per prompt |
| `head_sha` | SHA of the current HEAD commit |
| `created_at` | When the branch was created |
| `updated_at` | When HEAD last moved (i.e. last commit on this branch) |

### Operations

| Operation | What it does |
|---|---|
| **Commit** | Appends a new version; advances `head_sha` |
| **Create** | Makes a new branch starting from any existing SHA |
| **Merge** | Fast-forward only — moves `into_branch` HEAD to `from_branch` HEAD; creates a new commit on `into_branch` with `from_branch`'s content |
| **Rollback** | Creates a new commit restoring content from a past ref; advances HEAD to the rollback commit (history is preserved) |

> Cantica uses **fast-forward-only merges**. There are no merge commits. If you need to reconcile diverged histories, roll back one branch to a common ancestor and recommit.

### Examples

```bash
# List branches
cantica branch osteck/architect

# Create a new branch from the current HEAD
cantica branch osteck/architect experimental

# Commit onto the new branch
cantica commit osteck/architect -b experimental -m "Draft changes" -f draft.txt

# Diff the two branches
cantica diff osteck/architect main experimental

# Merge experimental into main
cantica merge osteck/architect --from experimental

# Roll back main to the v1.0 tag
cantica rollback osteck/architect v1.0 -b main
```

---

## 5. Tag

A **tag** is a named, immutable pointer to a specific version SHA. Use tags to mark stable releases (`v1.0`, `production`, `stable`) so consumers can pin to a known-good version without tracking a moving branch head.

```
versions:  v1  v2  v3  v4  v5
tags:           │       │
               v1.0   v2.0
```

### Fields

| Field | Description |
|---|---|
| `name` | Tag name; any string is valid |
| `sha` | The version SHA this tag points to |

### Difference from branches

| | Branch | Tag |
|---|---|---|
| Moves on commit | Yes | No |
| Use for | Active development | Stable releases |
| Re-assignable | Yes (via commit/merge/rollback) | Via upsert (explicit API call) |

### Examples

```bash
# Tag the current HEAD of main as v1.0
cantica tag osteck/architect v1.0

# Tag a specific SHA
cantica tag osteck/architect v1.1 --sha abc1234...

# Retrieve the tagged version
cantica show osteck/architect@v1.0

# List all tags
cantica log osteck/architect   # tags appear alongside each commit
```

---

## 6. Ref resolution

A **ref** is a string that resolves to a concrete version. Every endpoint and CLI command that takes `@ref` accepts all these forms:

| Ref | Example | Resolves to |
|---|---|---|
| `latest` | `osteck/architect@latest` | HEAD of the default branch (`main`) |
| Branch name | `osteck/architect@experimental` | HEAD of that branch |
| Tag name | `osteck/architect@v1.0` | Version the tag points to |
| Full SHA | `osteck/architect@a3f1d2e4...` | Exact version (64 hex chars) |
| SHA prefix | `osteck/architect@a3f1d2` | Version whose SHA starts with that prefix (unique match required) |

**Resolution order** (first match wins):
1. `"latest"` or default branch name → branch HEAD
2. Named tag → tag's SHA
3. Named branch → branch HEAD
4. Exact 64-char SHA
5. SHA prefix — exactly one match required; ambiguous prefix raises an error

When the `@ref` part is omitted entirely (`osteck/architect`), the behaviour is identical to `@latest`.

---

## 7. Blob store

The **blob store** is a content-addressable filesystem store for prompt text. It lives at `<vault_path>/objects/` and is completely separate from the database.

### Layout

```
~/.cantica/vault/
├── cantica.db              ← SQLite: all metadata
└── objects/
    ├── a3/
    │   └── b7c9e2f1d8...   ← content file (SHA: a3b7c9e2f1d8...)
    └── fc/
        └── 2d8e9a1b3c...
```

Files are named by the SHA-256 of their content, split at the 2-char prefix (matching git's loose object layout). This makes two things true:

1. **Deduplication is automatic.** Two versions with identical text share one file. Disk usage grows with unique content, not commit count.
2. **Content is immutable.** A file's name is its hash. Writing new content always writes a new file; existing files are never modified.

### Encryption

When a namespace is `encoded: true`, content is transparently encrypted before writing and decrypted after reading using AES-256-GCM. The namespace's encryption key is stored server-side and is never exposed via the API. From the caller's perspective, content appears in plaintext in API responses — encryption is purely a storage-layer guarantee.

---

## 8. Variables and rendering

Prompts support **template variables** using `{{double-brace}}` syntax. Variables allow a single prompt to serve many contexts with runtime substitution.

### Variable schema

Each variable is declared with a `VariableSchema` entry on the prompt (or captured as a snapshot per version):

| Field | Description |
|---|---|
| `name` | Variable name used in `{{name}}` placeholders |
| `type` | `"string"` (only type currently supported) |
| `description` | Human-readable hint shown to callers |
| `default` | Value used when no runtime value is supplied |
| `required` | If `true`, rendering fails with a 422 error when no value or default is present |

### Example prompt content

```
You are a senior {{role}} specialising in {{language}}.
Review the following code for correctness, style, and {{focus}}.
```

With schema:
```json
[
  { "name": "role",     "required": true  },
  { "name": "language", "default": "Python" },
  { "name": "focus",    "default": "readability" }
]
```

### Rendering

Rendering resolves a version and substitutes all placeholders:

```bash
# Uses defaults for language and focus
cantica render osteck/code-reviewer --var role=architect

# Override all three
cantica render osteck/code-reviewer \
  --var role=architect \
  --var language=TypeScript \
  --var focus="security vulnerabilities"
```

Output:
```
You are a senior architect specialising in TypeScript.
Review the following code for correctness, style, and security vulnerabilities.
```

**Substitution rules:**
1. If a runtime value is provided for a variable, use it.
2. Otherwise fall back to the variable's `default`.
3. If `required: true` and no value or default is available → error.
4. Placeholders with no matching schema entry are left as-is (no error).

Variable schemas are snapshotted per version. The variables declared on `v1.0` may differ from those on `v2.0` — callers rendering a specific ref get that version's schema.

---

## 9. Fork

A **fork** is a deep copy of a prompt that preserves the full commit history and records lineage. The fork becomes a fully independent prompt — new commits on the fork do not affect the source, and vice versa.

```
community/senior-architect
    │  (at source_sha abc123)
    └──fork──► osteck/my-architect
                  (independent from this point)
```

### What is copied

- All versions on the specified source branch (oldest-first)
- All tags pointing to those versions
- All prompt metadata (description, tags, model hints, license, variables)

SHAs are recomputed for the new `prompt_id`, so the fork's commit SHAs differ from the source's even when content is identical.

### Lineage tracking

The `Fork` record stores:
- `source_slug` — the original prompt's address
- `source_sha` — the HEAD SHA at fork time (a frozen reference to where the fork diverged)
- `fork_slug` — the new prompt's address

The source prompt's `fork_count` is incremented. Use `GET /v1/prompts/{ns}/{name}/forks` or `cantica fork-list ns/name` to enumerate all known forks.

### Examples

```bash
# Fork a community prompt into your namespace
cantica fork community/senior-architect osteck/my-architect

# The fork is now independent
cantica commit osteck/my-architect -m "My customisation" -f custom.txt

# The source is unaffected
cantica show community/senior-architect   # unchanged
```

---

## 10. Collection

A **collection** is a curated, named set of prompts — like a playlist. Collections are namespaced (`osteck/my-toolkit`) and their membership is mutable. There is no version control on collection membership itself.

```
osteck/engineering-toolkit
  ├── osteck/code-reviewer
  ├── osteck/architect
  └── community/senior-arch
```

Collections are useful for grouping prompts by project, team, theme, or use case. If you need to version a collection, create a dedicated prompt whose content describes the set.

### Examples

```bash
# API: create a collection
POST /v1/collections
{ "namespace": "osteck", "name": "engineering-toolkit" }

# API: add a prompt
POST /v1/collections/osteck/engineering-toolkit/items
{ "prompt_slug": "community/senior-arch" }

# API: list collections
GET /v1/collections?namespace=osteck

# API: view collection with all member prompts
GET /v1/collections/osteck/engineering-toolkit
```

---

## 11. Visibility

**Visibility** controls who can discover and access a prompt in listing and search operations.

| Value | Who can see it |
|---|---|
| `public` | Everyone — appears in global search and lists |
| `private` | Owner only — never in search or public lists |
| `unlisted` | Accessible by direct slug but never in lists or search |
| `team` | Owner's organisation (not yet enforced server-side; reserved for future use) |

Visibility is a per-prompt flag, independent of the namespace's `is_proprietary` or `encoded` flags. A `public` prompt in a `is_proprietary` namespace is still gated by the namespace certificate — visibility only affects listing behaviour, not access control.

**Search visibility rules:**
- `public` prompts in public namespaces are always returned.
- `private` and `unlisted` prompts never appear in search.
- Prompts in `is_proprietary` namespaces are excluded from search unless a valid `cert_token` is supplied.
- Prompts in `encoded` namespaces are always excluded from search.

---

## 12. Access control

Cantica has two independent access-control mechanisms: **API key authentication** for the server itself, and **namespace certificates** for proprietary namespaces.

### API key authentication

API key auth is **opt-in** and server-wide. Enable it with `CANTICA_AUTH_ENABLED=true`.

When enabled, every request must include:
```
X-API-Key: cantica_<256-bit-random>
```

Keys are generated via `POST /v1/tokens`. Only the SHA-256 hash of the raw key is stored — the raw key is shown exactly once at creation time. If lost, revoke the key and create a new one.

```bash
# Create a key
curl -X POST http://localhost:8042/v1/tokens \
  -H "Content-Type: application/json" \
  -d '{"name": "ci-pipeline"}'
# → {"id": "...", "key": "cantica_...", "created_at": "..."}
#   Save the key value — it is never shown again.

# Use it
curl http://localhost:8042/v1/prompts \
  -H "X-API-Key: cantica_..."
```

### Namespace certificates

Namespace certificates are for **proprietary namespaces** specifically. They are independent of API key auth — a server with auth disabled can still have proprietary namespaces that require certificates.

When a namespace is `is_proprietary: true`, every operation on any prompt, version, tag, branch, star, comment, fork, collection, diff, or render endpoint for that namespace requires:
```
X-Cantica-Certificate: <signed-token>
```

**Token format:**
```
base64url(json_payload) + "." + base64url(hmac_sha256_signature)
```

**Payload:**
```json
{
  "id":         "cert-uuid",
  "namespace":  "myorg",
  "granted_to": "alice",
  "issued_at":  "2026-05-23T10:00:00Z",
  "expires_at": null
}
```

The signature is HMAC-SHA256 over the payload using a per-instance secret key. Cantica verifies the signature, checks expiry, and confirms the certificate has not been revoked — all in constant time to prevent timing attacks.

**Certificate lifecycle:**

```bash
# Issue a certificate (the token is shown once and never again)
cantica cert-issue myorg --to alice
# ID:    c1d2e3f4-...
# Token: eyJuYW1lc3BhY2UiOiJteW9yZyJ9.abc123...

# List all certificates for a namespace
cantica cert-list myorg

# Revoke a certificate immediately
cantica cert-revoke c1d2e3f4-...
```

**Using a certificate in API calls:**
```bash
curl http://localhost:8042/v1/prompts/myorg/secret-prompt \
  -H "X-Cantica-Certificate: eyJuYW1lc3BhY2UiOiJteW9yZyJ9.abc123..."
```

**Using a certificate in push/pull:**
```bash
cantica push myorg/secret --remote https://cantica.example.com \
  --certificate eyJuYW1lc3BhY2UiOiJteW9yZyJ9.abc123...
```

**Publishing a proprietary namespace** (making it public again) also requires a valid certificate in the `PATCH /v1/namespaces/{name}` request — this prevents unauthorized actors from stripping the protection.

---

## 13. Stars and comments

### Stars

A **star** is a lightweight social signal. Any namespace can star any prompt (at most once). Stars are tracked for social discovery and contribute to `star_count` on the prompt.

```bash
cantica star community/senior-architect
cantica unstar community/senior-architect
```

### Comments

A **comment** is a text note on a prompt, optionally pinned to a specific version SHA. Comments support Markdown. They are useful for peer review, notes on quality, or coordination across teams.

```bash
# Comment on the prompt (not version-specific)
cantica comment osteck/architect "Great baseline — consider adding a {{tone}} variable."

# Comment pinned to a specific version
cantica comment osteck/architect "v1.1 phrasing works better for GPT-4o" --ref a3f1d2e4
```

---

## 14. Webhooks

A **webhook** is an HTTP callback that fires when events occur. Register a URL and Cantica will `POST` a signed JSON payload to it whenever a matching event is triggered.

### Supported events

| Event | Fires when |
|---|---|
| `version.created` | A new commit is made on any prompt |

### Payload

```json
{
  "event":       "version.created",
  "sha":         "a3f1d2e4...",
  "prompt_slug": "osteck/code-reviewer",
  "author":      "osteck",
  "message":     "add language variable",
  "created_at":  "2026-05-24T15:00:00Z"
}
```

### Signature verification

Every delivery includes:
```
X-Cantica-Signature: sha256=<hmac-hex>
```

Verify with: `HMAC-SHA256(secret, raw_request_body)` and compare in constant time.

### Scoping

Set `namespace` on the webhook to receive only events from a specific namespace. Leave it `null` to receive all events.

```json
POST /v1/hooks
{
  "url":       "https://my-service.example.com/cantica-hook",
  "events":    ["version.created"],
  "secret":    "my-signing-secret",
  "namespace": "osteck"
}
```

---

## 15. Federation — push and pull

Cantica instances can synchronise prompts with each other over HTTP. A **push** sends local versions to a remote instance; a **pull** fetches remote versions into the local vault.

### How it works

Push:
1. Enumerate all local versions on the branch.
2. Check which SHAs are already present on the remote.
3. `POST` only the missing versions (oldest-first, preserving SHAs via import mode).
4. Sync tags.

Pull:
1. `GET` prompt metadata from the remote.
2. `GET` version list (oldest-first) from the remote.
3. Import each version locally, verifying that the computed SHA matches the declared SHA.
4. Sync tags.

Because SHAs are deterministically computed from content, author, message, and timestamp, imported versions are identical and independently verifiable — no trust required beyond the initial transfer.

### Proprietary remotes

When the remote namespace is proprietary, pass the certificate token:

```bash
cantica push myorg/secret --remote https://cantica.example.com --certificate <token>
cantica pull myorg/secret --remote https://cantica.example.com --certificate <token>
```

### Lock files

The `lock` and `install` commands support **pinned deployments** — resolving `cantica://` URIs to exact SHAs and storing them in a lock file:

```bash
# Resolve all cantica:// URIs in a config to their current SHAs
cantica lock cantica://osteck/architect@latest \
             cantica://community/reviewer@v1.0 \
  --output prompts.lock.toml

# Later: fetch exactly those pinned versions
cantica install --lock prompts.lock.toml
```

This gives reproducible prompt deployments: lock files capture exact SHAs and can be committed to source control.

---

## 16. Addressing scheme

Every prompt version is uniquely addressable with a compact string. The general form is:

```
namespace/name@ref
```

| Form | Example | Meaning |
|---|---|---|
| `namespace/name` | `osteck/architect` | Latest version on the default branch |
| `namespace/name@latest` | `osteck/architect@latest` | Same as above (explicit) |
| `namespace/name@branchname` | `osteck/architect@experimental` | HEAD of a named branch |
| `namespace/name@tagname` | `osteck/architect@v1.0` | A stable tagged release |
| `namespace/name@sha` | `osteck/architect@a3f1d2e4` | An exact commit (full or abbreviated SHA) |
| `cantica://namespace/name@ref` | `cantica://osteck/architect@v1.0` | Full URI (used by external tools and the `resolve` endpoint) |
| `cantica://host/namespace/name@ref` | `cantica://api.example.com/osteck/arch@latest` | Remote URI (federated resolution) |

The `cantica://` scheme is designed for use in agent configs and lock files where the address must be unambiguous even when not inside a Cantica-aware tool.

---

## 17. Shim — library embedding

The **shim** (`CanticaShim`) is an embeddable library that lets any FastAPI application use a local Cantica vault without running a separate server process. All operations are direct function calls into `VersionStore` — no HTTP round-trips.

### Setup

```python
from cantica.shim import CanticaShim
from contextlib import asynccontextmanager
from fastapi import FastAPI

shim = CanticaShim(vault_path="/path/to/vault")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shim.lifespan():
        yield

app = FastAPI(lifespan=lifespan)
shim.mount(app, prefix="/api/v1")  # optionally mount all Cantica routes
```

### Programmatic access

```python
# Create a prompt and commit a version
prompt = await shim.prompts.create("acme", "my-prompt")
version = await shim.versions.commit(
    "acme", "my-prompt",
    content="You are a {{role}}.",
    message="Initial",
    author="acme",
)

# Render with variables
rendered = await shim.versions.render(
    "acme", "my-prompt",
    variables={"role": "senior architect"},
)
print(rendered)   # "You are a senior architect."
```

### Async contract

All shim methods are `async`. Internally they run synchronous `VersionStore` operations on a thread pool so they do not block the event loop.

The shim exposes namespaced facades:

| Facade | What it wraps |
|---|---|
| `shim.namespaces` | Namespace create/list/get |
| `shim.prompts` | Prompt CRUD |
| `shim.versions` | Commit, resolve, render, diff |
| `shim.branches` | Branch create, merge, rollback |
| `shim.tags` | Tag create/list |
| `shim.forks` | Fork and lineage |
| `shim.stars` | Star / unstar |
| `shim.comments` | Comment CRUD |
| `shim.collections` | Collection and membership |
| `shim.webhooks` | Webhook registration |
| `shim.auth` | API key management |
| `shim.certificates` | Namespace certificate lifecycle |
| `shim.export` | Push / pull between instances |

---

## Concept map

```
Namespace
  ├── owns many Prompts
  │     ├── has many Versions (git-style commits, immutable)
  │     │     └── content stored in BlobStore (content-addressable)
  │     ├── has many Branches (mutable HEAD pointers)
  │     ├── has many Tags (immutable named pointers to SHAs)
  │     ├── has many Stars (social signals)
  │     ├── has many Comments (optionally pinned to a Version)
  │     └── has many Forks (lineage records)
  ├── owns many Collections (curated sets of Prompts)
  └── owns many Certificates (access tokens for proprietary namespaces)
```

---

*For HTTP endpoint details see [api-manual.md](api-manual.md). For quick-start examples see the project [README](../README.md).*
