# Cantica API — Developer Manual

> **Base URL:** `http://localhost:8042`
> **API prefix:** `/v1`
> **Interactive docs:** [`/docs`](http://localhost:8042/docs) (Swagger UI) · [`/redoc`](http://localhost:8042/redoc) (ReDoc)

---

## Table of contents

1. [Core concepts](#1-core-concepts)
2. [Data models](#2-data-models)
3. [Authentication](#3-authentication)
4. [Namespaces](#4-namespaces)
5. [Meta endpoints](#5-meta-endpoints)
6. [Prompts](#6-prompts)
7. [Versions](#7-versions)
8. [Branches](#8-branches)
9. [Tags](#9-tags)
10. [Forks](#10-forks)
11. [Diff](#11-diff)
12. [Stars](#12-stars)
13. [Comments](#13-comments)
14. [Collections](#14-collections)
15. [Render](#15-render)
16. [Resolve](#16-resolve)
17. [Webhooks](#17-webhooks)
18. [Auth tokens](#18-auth-tokens)
19. [Error reference](#19-error-reference)
20. [Swagger UI guide](#20-swagger-ui-guide)

---

## 1. Core concepts

> This section is a quick reference. For precise definitions, SHA computation details, worked examples, and the full concept map see **[docs/concepts.md](concepts.md)**.

```mermaid
graph LR
    Namespace -->|"owns"| Prompt
    Namespace -->|"owns"| Collection
    Namespace -->|"issues"| Certificate
    Prompt -->|"has many"| Version
    Prompt -->|"has many"| Branch
    Prompt -->|"has many"| Tag
    Prompt -->|"has many"| Fork
    Prompt -->|"has many"| Star
    Prompt -->|"has many"| Comment
    Collection -->|"contains many"| Prompt
    Branch -->|"points to HEAD"| Version
    Tag -->|"points to"| Version
    Version -->|"content in"| BlobStore
    Version -->|"parent"| Version
```

### Namespace

A **Namespace** is the owner-level scope for prompts and collections — the `osteck` part of `osteck/code-reviewer`. Namespaces are created explicitly and carry two access-control flags:

- **`is_proprietary`** — when `true`, every operation on this namespace's prompts, versions, tags, branches, stars, comments, forks, collections, diffs, and renders requires a valid `X-Cantica-Certificate` header. Without it the server returns `403 Forbidden`. Proprietary namespaces are excluded from global search unless a valid certificate is supplied with the search query.
- **`encoded`** — when `true`, all version content is encrypted at rest with AES-256-GCM. Encoded namespace content is always excluded from search results.

### Prompt

A **Prompt** is the primary object: metadata (`description`, `tags`, `model_hints`, `license`, `visibility`) plus a full version history. Identified by its **slug**: `{namespace}/{name}`.

### Version (commit)

Every time prompt content is saved, a **Version** is created. Versions are immutable commits:

- Each version has a unique **SHA** derived from content hash, parent SHA, author, message, and timestamp — modifications to any field produce a different SHA
- Versions form a singly-linked list via `parent_sha` (history is fully traversable)
- Content lives in the **blob store** (content-addressable, deduplicated); only `content_sha` is in the database

```
main:  v1 ──► v2 ──► v3 (HEAD)
               │
               └──► v4 ──► v5 (HEAD of "experimental")
```

### Branch

A **Branch** is a named, mutable pointer to the HEAD of a chain of versions. Every prompt starts with `main`. Branch operations:

- **Commit** — appends a version and advances the HEAD
- **Create** — makes a new branch from any existing SHA
- **Merge** — fast-forward only: moves `into_branch` HEAD to `from_branch` HEAD
- **Rollback** — creates a new commit restoring content from a past ref (history preserved)

### Tag

A **Tag** is a named, immutable pointer to a specific version SHA. Tags never move automatically. Use them for stable releases (`v1.0`, `production`, `stable`).

### Ref

A **ref** resolves to a concrete version. Accepted forms, resolved in this order:

| Form | Example | Resolves to |
|---|---|---|
| `latest` | `osteck/arch@latest` | HEAD of default branch |
| Branch name | `osteck/arch@experimental` | Branch HEAD |
| Tag name | `osteck/arch@v1.0` | Tagged version |
| Full SHA | `osteck/arch@a3f1d2e4...` | Exact version |
| SHA prefix | `osteck/arch@a3f1d2` | Unique prefix match |

### Blob store

Content-addressable filesystem store at `<vault>/objects/`. Files are named by the SHA-256 of their content (2-char prefix split, matching git's loose object layout). Content is deduplicated — two versions with identical text share one blob.

### Variables and rendering

Prompt content can contain `{{variable_name}}` placeholders. Variables are declared in the prompt's schema with `name`, `default`, `required`, and `description` fields. The **render** operation substitutes placeholder values at call time, using defaults for any not supplied and raising a 422 error for missing required variables.

### Fork

A **Fork** deep-copies a prompt (full history + metadata) into a new slug. The fork is independent from the moment it is created. Lineage is tracked: `source_slug` and `source_sha` are recorded, and the source's `fork_count` is incremented.

### Collection

A **Collection** is a named, mutable set of prompts (`osteck/my-toolkit`). Collections do not version-control their membership. To version a collection, commit a dedicated prompt describing the set.

### Diff

**Diff** returns a unified diff string between any two refs of a prompt — the same format as `git diff`.

### Render

**Render** resolves a prompt at a given ref and substitutes all `{{variable}}` placeholders. Returns ready-to-use content.

### URI resolution

Prompts are addressable by `cantica://` URIs — the scheme used by songbook agents and the lock-file workflow:

```
cantica://osteck/code-reviewer@v1.3
cantica://community/senior-architect@latest
cantica://osteck/my-prompt@abc123f
```

`POST /v1/resolve` parses a URI and returns the resolved `Version`. An optional `remote_url` enables resolution against a remote Cantica instance.

### Webhook

A **Webhook** is an HTTP callback for event delivery. Cantica POSTs a signed JSON payload (HMAC-SHA256 in `X-Cantica-Signature`) to the registered URL. Supported event: `version.created`.

---

## 2. Data models

### Namespace

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Unique namespace identifier |
| `description` | `string` | Human-readable description |
| `is_proprietary` | `boolean` | Requires an access certificate for all operations |
| `encoded` | `boolean` | Content encrypted at rest with AES-256-GCM |
| `created_at` | `datetime` | ISO 8601 UTC |

### Certificate

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Unique certificate identifier |
| `namespace` | `string` | Namespace this certificate grants access to |
| `granted_to` | `string` | Identifier of the grantee |
| `issued_at` | `datetime` | ISO 8601 UTC |
| `expires_at` | `datetime \| null` | Expiry time, or `null` if non-expiring |
| `revoked` | `boolean` | Whether the certificate has been revoked |
| `token` | `string \| null` | HMAC-signed token — returned **once** at issuance, `null` in subsequent list responses |

### Prompt

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Unique identifier |
| `namespace` | `string` | Owner namespace |
| `name` | `string` | Prompt name (unique within namespace) |
| `slug` | `string` | Computed: `namespace/name` |
| `description` | `string` | Short human-readable description |
| `tags` | `string[]` | Searchable labels |
| `model_hints` | `string[]` | Suggested model identifiers (e.g. `gpt-4o`) |
| `license` | `string` | SPDX identifier, default `MIT` |
| `visibility` | `enum` | `public` · `private` · `unlisted` · `team` |
| `variables` | `VariableSchema[]` | Declared template variables |
| `star_count` | `integer` | Cached count of stars |
| `fork_count` | `integer` | Cached count of forks |
| `default_branch` | `string` | Default branch name, usually `main` |
| `created_at` | `datetime` | ISO 8601 UTC |
| `updated_at` | `datetime` | ISO 8601 UTC |

### Version

| Field | Type | Description |
|---|---|---|
| `sha` | `string` | Unique commit SHA (sha256 hex) |
| `prompt_id` | `string (UUID)` | Parent prompt |
| `branch` | `string` | Branch this version lives on |
| `parent_sha` | `string \| null` | Previous version SHA (null for root) |
| `message` | `string` | Commit message |
| `author` | `string` | Author identifier |
| `content` | `string` | Full prompt text |
| `variables` | `VariableSchema[]` | Variable schema snapshot at this version |
| `tags` | `string[]` | Tag names pointing to this SHA |
| `created_at` | `datetime` | ISO 8601 UTC |

### Branch

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Branch name |
| `prompt_id` | `string (UUID)` | Owning prompt |
| `head_sha` | `string` | SHA of the current HEAD |
| `created_at` | `datetime` | ISO 8601 UTC |
| `updated_at` | `datetime` | ISO 8601 UTC |

### Tag

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Tag name (e.g. `v1.0`) |
| `prompt_id` | `string (UUID)` | Owning prompt |
| `sha` | `string` | Version SHA this tag points to |
| `created_at` | `datetime` | ISO 8601 UTC |

### Fork

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Unique identifier |
| `source_slug` | `string` | `namespace/name` of the source prompt |
| `source_sha` | `string` | SHA at time of forking |
| `fork_slug` | `string` | `namespace/name` of the new fork |
| `created_at` | `datetime` | ISO 8601 UTC |

### Collection

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Unique identifier |
| `namespace` | `string` | Owner namespace |
| `name` | `string` | Collection name |
| `description` | `string` | Human-readable description |
| `created_at` | `datetime` | ISO 8601 UTC |

### VariableSchema

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Variable name (used in `{{name}}`) |
| `type` | `string` | `string` (only type currently supported) |
| `description` | `string` | Human-readable hint |
| `default` | `any \| null` | Default value (used when not supplied at render time) |
| `required` | `boolean` | If true, render fails without a value or default |

### Visibility

| Value | Description |
|---|---|
| `public` | Visible to everyone |
| `private` | Visible only to owner |
| `unlisted` | Accessible by direct link but not listed |
| `team` | Visible within the owner's organisation |

---

## 3. Authentication

Authentication is **opt-in**. It is disabled by default and can be enabled with `CANTICA_AUTH_ENABLED=true`.

### When auth is disabled

Every request is treated as the `local` user. No headers are required.

### When auth is enabled

Pass a raw API key in the `X-API-Key` header:

```
X-API-Key: cntk_xxxxxxxxxxxxxxxxxxxx
```

The raw key is shown **exactly once** at creation time ([`POST /v1/tokens`](#post-v1tokens)). Only the SHA-256 hash of the key is stored. If lost, revoke and re-create.

### Namespace certificates (`X-Cantica-Certificate`)

A second, orthogonal access mechanism is used for **proprietary namespaces**. This is independent of API-key auth.

When a namespace is created with `is_proprietary: true`, the Cantica instance that owns the namespace can issue **certificates** — HMAC-SHA256 signed tokens that grant access to the namespace's resources. The certificate token is passed in a request header:

```
X-Cantica-Certificate: <token>
```

The token is returned exactly once when the certificate is issued ([`POST /v1/namespaces/{name}/certificates`](#post-v1namespaces-name-certificates)). Store it securely.

**Endpoints that enforce certificate access:**

Any endpoint that addresses a proprietary namespace — prompts, versions, tags, branches, stars, comments, forks, collections, diff, and render — returns `403 Forbidden` if the certificate header is absent or invalid.

**Push/pull with certificates:**

When pushing to or pulling from a proprietary remote namespace, pass the certificate with `--certificate`:

```bash
cantica push myorg/secret --remote https://cantica.example.com --certificate <token>
cantica pull myorg/secret --remote https://cantica.example.com --certificate <token>
```

### Swagger UI authentication

1. Open [`/docs`](http://localhost:8042/docs)
2. Click the **Authorize** button (🔒) at the top right
3. Enter your API key in the `X-API-Key` field
4. Click **Authorize** — all subsequent requests from the UI will include the header

---

## 4. Namespaces

Namespaces are the owner-level containers for prompts and collections. They are explicit objects with their own metadata and access-control flags.

**CLI equivalents:**

| CLI command | Equivalent API call |
|---|---|
| `cantica namespace-new NAME [--proprietary] [--encoded]` | `POST /v1/namespaces` |
| `cantica namespace-list` | `GET /v1/namespaces` |
| `cantica cert-issue NS --to GRANTEE` | `POST /v1/namespaces/{name}/certificates` |
| `cantica cert-list NS` | `GET /v1/namespaces/{name}/certificates` |
| `cantica cert-revoke CERT_ID` | `DELETE /v1/namespaces/{name}/certificates/{id}` |

---

### `GET /v1/namespaces`

List all namespaces.

**Response `200`** — `NamespaceResponse[]`

```json
[
  {
    "name": "osteck",
    "description": "Personal prompts",
    "is_proprietary": false,
    "encoded": false,
    "created_at": "2026-05-24T10:00:00Z"
  }
]
```

---

### `POST /v1/namespaces`

Create a namespace. Creating the same namespace twice is idempotent — a second `POST` with the same `name` returns `201` without modifying the existing record.

**Request body**

```json
{
  "name": "myorg",
  "description": "My organisation's prompt library",
  "is_proprietary": false,
  "encoded": false
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | ✅ | — | Unique namespace identifier |
| `description` | ❌ | `""` | Human-readable description |
| `is_proprietary` | ❌ | `false` | Require a certificate for all access |
| `encoded` | ❌ | `false` | Encrypt all version content at rest |

**Response `201`** — `NamespaceResponse`

> **Note:** When `encoded: true`, the server generates a 256-bit AES encryption key at creation time. This key is stored server-side and is never exposed through the API.

---

### `GET /v1/namespaces/{name}`

Retrieve a namespace by name.

**Response `200`** — `NamespaceResponse`
**Response `404`** — Namespace not found

---

### `PATCH /v1/namespaces/{name}`

Update namespace metadata. Supports partial update — omit fields you do not want to change.

**Request body**

```json
{
  "description": "Updated description",
  "is_proprietary": false
}
```

| Field | Description |
|---|---|
| `description` | New description |
| `is_proprietary` | Set to `false` to **publish** a proprietary namespace (see below) |

**Publishing a proprietary namespace:**

Setting `is_proprietary` from `true` to `false` ("publishing") requires a valid `X-Cantica-Certificate` header for that namespace. Without it the server returns `403 Forbidden`. This prevents unauthorized actors from making a proprietary namespace public.

**Response `200`** — `NamespaceResponse`
**Response `403`** — Publishing requires a valid certificate
**Response `404`** — Namespace not found

---

### `POST /v1/namespaces/{name}/certificates`

Issue an access certificate for a proprietary namespace. The one-time `token` field is included in the response and must be saved by the caller — it is never retrievable again.

**Request body**

```json
{
  "granted_to": "alice",
  "expires_at": null
}
```

| Field | Required | Description |
|---|---|---|
| `granted_to` | ✅ | Identifier of the grantee (user, service, team) |
| `expires_at` | ❌ | ISO 8601 UTC expiry; omit or `null` for non-expiring |

**Response `201`** — `CertificateResponse` (with `token`)

```json
{
  "id": "c1d2e3f4-...",
  "namespace": "myorg",
  "granted_to": "alice",
  "issued_at": "2026-05-25T09:00:00Z",
  "expires_at": null,
  "revoked": false,
  "token": "eyJuYW1lc3BhY2UiOiAibXlvcmcifQ.3b4c5d6e..."
}
```

> ⚠️ **Save the `token` immediately.** It is shown only once. Revoking and re-issuing creates a new certificate with a new token.

**Response `404`** — Namespace not found
**Response `409`** — Namespace is not proprietary (certificates are only meaningful for proprietary namespaces)

---

### `GET /v1/namespaces/{name}/certificates`

List all certificates for a namespace. The `token` field is always `null` in list responses — only the issuance response includes the token.

**Response `200`** — `CertificateResponse[]` (all `token` fields are `null`)

```json
[
  {
    "id": "c1d2e3f4-...",
    "namespace": "myorg",
    "granted_to": "alice",
    "issued_at": "2026-05-25T09:00:00Z",
    "expires_at": null,
    "revoked": false,
    "token": null
  }
]
```

**Response `404`** — Namespace not found

---

### `DELETE /v1/namespaces/{name}/certificates/{cert_id}`

Revoke a certificate immediately. Requests using the revoked token will receive `403 Forbidden`.

**Response `204`** — Revoked
**Response `404`** — Namespace or certificate not found

---

## 5. Meta endpoints

### `GET /health`

Health check. Returns `200 OK` if the server is running.

**Response `200`**
```json
{ "status": "ok" }
```

---

### `GET /.well-known/cantica.json`

Service discovery document. Used by clients and federation partners to locate the API.

**Response `200`**
```json
{
  "version": "0.1",
  "api_url": "/v1",
  "webhooks_url": "/v1/hooks"
}
```

---

## 6. Prompts

Prompts are the top-level objects. A prompt holds metadata and owns a version history.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `GET /v1/prompts`

List or search prompts. Returns all prompts when called with no parameters, or applies filters.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | `string` | Filter by namespace |
| `q` | `string` | Full-text search query (searches name, description, content) |
| `tag` | `string` | Filter to prompts that include this tag |
| `model` | `string` | Filter to prompts that list this model hint |
| `visibility` | `string` | Filter by visibility (`public`, `private`, `unlisted`, `team`) |
| `cert_token` | `string` | Certificate token — includes matching proprietary namespace in search results |

**Search visibility rules:**

- Public, non-encoded namespaces are always searchable.
- Proprietary namespace prompts are excluded from search unless a valid `cert_token` is provided for that namespace.
- Encoded namespace prompts are always excluded from search results.

**Response `200`** — `PromptResponse[]`

```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "namespace": "osteck",
    "name": "code-reviewer",
    "slug": "osteck/code-reviewer",
    "description": "Reviews code for correctness and style",
    "tags": ["engineering", "review"],
    "model_hints": ["gpt-4o", "claude-opus-4"],
    "license": "MIT",
    "visibility": "public",
    "variables": [],
    "star_count": 12,
    "fork_count": 3,
    "default_branch": "main",
    "created_at": "2026-05-24T10:00:00Z",
    "updated_at": "2026-05-24T11:30:00Z"
  }
]
```

---

### `POST /v1/prompts`

Create a new prompt. The `namespace/name` combination must be unique.

**Request body**

```json
{
  "namespace": "osteck",
  "name": "code-reviewer",
  "description": "Reviews code for correctness and style",
  "tags": ["engineering", "review"],
  "model_hints": ["gpt-4o"],
  "license": "MIT",
  "visibility": "public",
  "variables": [
    {
      "name": "language",
      "type": "string",
      "description": "Programming language to review",
      "default": "Python",
      "required": false
    }
  ]
}
```

| Field | Required | Default |
|---|---|---|
| `namespace` | ✅ | — |
| `name` | ✅ | — |
| `description` | ❌ | `""` |
| `tags` | ❌ | `[]` |
| `model_hints` | ❌ | `[]` |
| `license` | ❌ | `"MIT"` |
| `visibility` | ❌ | `"public"` |
| `variables` | ❌ | `[]` |

**Response `201`** — `PromptResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `409`** — Prompt already exists

---

### `GET /v1/prompts/{namespace}/{name}`

Retrieve a single prompt by its slug.

**Response `200`** — `PromptResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

### `DELETE /v1/prompts/{namespace}/{name}`

Permanently delete a prompt and all its versions, branches, tags, stars, comments, and forks.

**Response `204`** — Deleted
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

## 7. Versions

Versions are the immutable commits of a prompt's content. Each commit advances the HEAD of its branch.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `GET /v1/prompts/{namespace}/{name}/versions`

List the commit history for a prompt on a given branch (newest first).

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `branch` | `string` | `main` | Branch to read history from |

**Response `200`** — `VersionResponse[]`

```json
[
  {
    "sha": "a3f1d2e4...",
    "prompt_id": "3fa85f64-...",
    "branch": "main",
    "parent_sha": "b1c2d3e4...",
    "message": "tighten instructions for edge cases",
    "author": "osteck",
    "content": "You are a code reviewer...",
    "variables": [],
    "tags": ["v1.1"],
    "created_at": "2026-05-24T11:00:00Z"
  }
]
```

---

### `POST /v1/prompts/{namespace}/{name}/versions`

Commit a new version of the prompt. Advances the branch HEAD.

**Request body**

```json
{
  "content": "You are a senior code reviewer specialising in {{language}}.",
  "message": "add language variable",
  "author": "osteck",
  "branch": "main",
  "variables": [
    {
      "name": "language",
      "type": "string",
      "default": "Python",
      "required": false
    }
  ]
}
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `content` | ✅ | — | Full prompt text |
| `message` | ✅ | — | Commit message |
| `author` | ✅ | — | Author identifier |
| `branch` | ❌ | `"main"` | Target branch |
| `variables` | ❌ | `[]` | Updated variable schema |
| `sha` | ❌ | — | **Import mode** — preserve SHA across instances |
| `parent_sha` | ❌ | — | **Import mode** — explicit parent |
| `created_at` | ❌ | — | **Import mode** — preserve original timestamp |

> **Import mode:** When `sha`, `parent_sha`, and `created_at` are all provided, the server calls `import_version()` instead of `commit()`, preserving the exact SHA. Useful for migrating prompts between Cantica instances without rewriting history. Returns `409` if the SHA already exists.

**Response `201`** — `VersionResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found
**Response `409`** — SHA conflict (import mode only)

---

### `GET /v1/prompts/{namespace}/{name}/versions/{ref}`

Retrieve a specific version by ref. A ref can be:

| Ref format | Example | Resolves to |
|---|---|---|
| Branch name | `main`, `experimental` | HEAD of that branch |
| Tag name | `v1.0`, `stable` | Version the tag points to |
| Full SHA | `a3f1d2e4c5...` | Exact version |
| Abbreviated SHA | `a3f1d2` | Version with matching SHA prefix |
| `latest` | `latest` | HEAD of `main` |

**Response `200`** — `VersionResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Ref not found

---

## 8. Branches

Branches are named pointers to version HEADs, scoped per prompt.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

```mermaid
gitGraph
   commit id: "v1"
   commit id: "v2"
   branch experimental
   checkout experimental
   commit id: "v3-exp"
   commit id: "v4-exp"
   checkout main
   commit id: "v3"
   merge experimental id: "merge"
```

---

### `GET /v1/prompts/{namespace}/{name}/branches`

List all branches for a prompt.

**Response `200`** — `BranchResponse[]`

```json
[
  {
    "name": "main",
    "prompt_id": "3fa85f64-...",
    "head_sha": "a3f1d2e4...",
    "created_at": "2026-05-24T10:00:00Z",
    "updated_at": "2026-05-24T12:00:00Z"
  }
]
```

---

### `POST /v1/prompts/{namespace}/{name}/branches`

Create a new branch starting from a specific commit SHA.

**Request body**

```json
{
  "name": "experimental",
  "from_sha": "a3f1d2e4c5b6..."
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | New branch name |
| `from_sha` | ✅ | SHA to branch from |

**Response `201`** — `BranchResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt or SHA not found

---

### `POST /v1/prompts/{namespace}/{name}/rollback`

Roll a branch back to any previous ref. Creates a new commit that restores the content at the target ref, preserving full history. The branch HEAD advances to the new rollback commit.

**Request body**

```json
{
  "ref": "v1.0",
  "branch": "main"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `ref` | ✅ | — | Target ref to restore (tag, SHA, branch name) |
| `branch` | ❌ | `"main"` | Branch to roll back |

**Response `200`** — `VersionResponse` (the new rollback commit)
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Ref not found

---

### `POST /v1/prompts/{namespace}/{name}/merge`

Merge one branch into another. Takes the HEAD content of `from_branch` and commits it onto `into_branch`. Returns a `409` if the branches are already at the same SHA (nothing to merge).

**Request body**

```json
{
  "from_branch": "experimental",
  "into_branch": "main"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `from_branch` | ✅ | — | Source branch |
| `into_branch` | ❌ | `"main"` | Target branch |

**Response `200`** — `MergeResponse` (a `VersionResponse` for the new merge commit)
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Branch or prompt not found
**Response `409`** — Nothing to merge (branches already at same HEAD)

---

## 9. Tags

Tags are immutable named pointers to specific version SHAs. Use them to mark stable releases.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `GET /v1/prompts/{namespace}/{name}/tags`

List all tags for a prompt.

**Response `200`** — `TagResponse[]`

```json
[
  {
    "name": "v1.0",
    "prompt_id": "3fa85f64-...",
    "sha": "a3f1d2e4...",
    "created_at": "2026-05-24T12:00:00Z"
  }
]
```

---

### `POST /v1/prompts/{namespace}/{name}/tags`

Create a new tag pointing to a specific SHA.

**Request body**

```json
{
  "name": "v1.0",
  "sha": "a3f1d2e4c5b6..."
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Tag name |
| `sha` | ✅ | Version SHA to tag |

**Response `201`** — `TagResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt or SHA not found

---

## 10. Forks

Forking copies a prompt's content at a branch HEAD into a new `namespace/name` slug. The fork is a fully independent prompt with tracked lineage.

> **Access control:** Forking a proprietary namespace prompt or forking into a proprietary namespace requires a valid `X-Cantica-Certificate` header; otherwise `403 Forbidden` is returned.

```mermaid
graph LR
    A["community/senior-architect\n(source_sha: abc123)"] -->|fork| B["osteck/my-architect\n(independent history)"]
```

---

### `POST /v1/prompts/{namespace}/{name}/fork`

Fork a prompt into a new slug.

**Request body**

```json
{
  "dest_namespace": "osteck",
  "dest_name": "my-architect",
  "branch": "main"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `dest_namespace` | ✅ | — | Target namespace for the fork |
| `dest_name` | ✅ | — | Target name for the fork |
| `branch` | ❌ | `"main"` | Branch of the source to fork from |

**Response `201`** — `ForkResponse`

```json
{
  "id": "7bc34d12-...",
  "source_slug": "community/senior-architect",
  "source_sha": "a3f1d2e4...",
  "fork_slug": "osteck/my-architect",
  "created_at": "2026-05-24T13:00:00Z"
}
```

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Source prompt not found
**Response `409`** — Destination slug already exists

---

### `GET /v1/prompts/{namespace}/{name}/forks`

List all known forks of a prompt.

**Response `200`** — `ForkResponse[]`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

## 11. Diff

Compute the unified diff between any two versions of a prompt.

> **Access control:** Returns `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `POST /v1/prompts/{namespace}/{name}/diff`

**Request body**

```json
{
  "ref1": "v1.0",
  "ref2": "main"
}
```

Both `ref1` and `ref2` accept any valid ref (tag, SHA, branch name, `latest`).

**Response `200`** — `DiffResponse`

```json
{
  "diff": "--- v1.0\n+++ main\n@@ -1,3 +1,4 @@\n You are a code reviewer.\n-Review for style.\n+Review for style and correctness.\n+Focus on {{language}} idioms.",
  "ref1": "v1.0",
  "ref2": "main",
  "namespace": "osteck",
  "name": "code-reviewer"
}
```

The `diff` field is a standard unified diff string with `---`/`+++` headers and `@@` context hunks. Empty string if the versions are identical.

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt or ref not found

---

## 12. Stars

Stars are a lightweight social signal — a user can star any prompt they find useful.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `POST /v1/prompts/{namespace}/{name}/star`

Star a prompt. The acting user's ID is taken from the auth context (or `"local"` when auth is disabled).

**Response `201`** — `StarResponse`

```json
{
  "id": "9d8e7f6a-...",
  "namespace": "local",
  "prompt_id": "3fa85f64-...",
  "created_at": "2026-05-24T14:00:00Z"
}
```

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

### `DELETE /v1/prompts/{namespace}/{name}/star`

Remove a star from a prompt.

**Response `204`** — Unstarred
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found or not starred

---

### `GET /v1/prompts/{namespace}/{name}/stargazers`

List all stargazers for a prompt.

**Response `200`** — `StarResponse[]`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

## 13. Comments

Comments can be left on a prompt in general, or pinned to a specific version SHA.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `POST /v1/prompts/{namespace}/{name}/comments`

Add a comment. The `version_sha` field optionally pins the comment to a specific version.

**Request body**

```json
{
  "body": "The phrasing in v1.1 is much clearer for GPT-4.",
  "version_sha": "a3f1d2e4..."
}
```

| Field | Required | Description |
|---|---|---|
| `body` | ✅ | Comment text (markdown supported) |
| `version_sha` | ❌ | Pin to a specific version |

**Response `201`** — `CommentResponse`

```json
{
  "id": "c1d2e3f4-...",
  "prompt_id": "3fa85f64-...",
  "version_sha": "a3f1d2e4...",
  "author": "local",
  "body": "The phrasing in v1.1 is much clearer for GPT-4.",
  "created_at": "2026-05-24T14:30:00Z"
}
```

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

### `GET /v1/prompts/{namespace}/{name}/comments`

List comments on a prompt, optionally filtered to a specific version.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `version_sha` | `string` | Only return comments pinned to this SHA |

**Response `200`** — `CommentResponse[]`
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt not found

---

### `DELETE /v1/prompts/{namespace}/{name}/comments/{comment_id}`

Delete a comment by its ID.

**Response `204`** — Deleted
**Response `403`** — Proprietary namespace requires certificate

---

## 14. Collections

Collections are named, curated sets of prompts grouped under a namespace.

> **Access control:** All endpoints in this section return `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `POST /v1/collections`

Create a new collection.

**Request body**

```json
{
  "namespace": "osteck",
  "name": "engineering-toolkit",
  "description": "All prompts I use for code review and architecture"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `namespace` | ✅ | — | Owner namespace |
| `name` | ✅ | — | Collection name (unique per namespace) |
| `description` | ❌ | `""` | Human-readable description |

**Response `201`** — `CollectionResponse`
**Response `403`** — Proprietary namespace requires certificate
**Response `409`** — Collection name already exists in this namespace

---

### `GET /v1/collections`

List collections, optionally filtered by namespace.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `namespace` | `string` | Filter to a specific namespace |

**Response `200`** — `CollectionResponse[]`

```json
[
  {
    "id": "e5f6a7b8-...",
    "namespace": "osteck",
    "name": "engineering-toolkit",
    "description": "All prompts I use for code review and architecture",
    "created_at": "2026-05-24T10:00:00Z"
  }
]
```

---

### `GET /v1/collections/{namespace}/{name}`

Get a collection with its full list of member prompts.

**Response `200`** — `CollectionDetail`

```json
{
  "id": "e5f6a7b8-...",
  "namespace": "osteck",
  "name": "engineering-toolkit",
  "description": "All prompts I use for code review and architecture",
  "created_at": "2026-05-24T10:00:00Z",
  "items": [
    { "id": "3fa85f64-...", "namespace": "osteck", "name": "code-reviewer", ... },
    { "id": "4ab12cd3-...", "namespace": "community", "name": "senior-architect", ... }
  ]
}
```

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Collection not found

---

### `DELETE /v1/collections/{namespace}/{name}`

Delete a collection. Member prompts are not affected.

**Response `204`** — Deleted
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Collection not found

---

### `POST /v1/collections/{namespace}/{name}/items`

Add a prompt to a collection by its slug.

**Request body**

```json
{
  "prompt_slug": "community/senior-architect"
}
```

**Response `204`** — Added
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Collection or prompt not found

---

### `DELETE /v1/collections/{namespace}/{name}/items/{prompt_namespace}/{prompt_name}`

Remove a prompt from a collection.

**Response `204`** — Removed
**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Collection or prompt not found

---

## 15. Render

Render resolves a prompt at a specific ref and fills in all `{{variable}}` placeholders.

> **Access control:** Returns `403 Forbidden` when the target namespace is proprietary and the request does not include a valid `X-Cantica-Certificate` header.

---

### `POST /v1/render`

**Request body**

```json
{
  "slug": "osteck/code-reviewer",
  "ref": "v1.1",
  "variables": {
    "language": "TypeScript"
  }
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `slug` | ✅ | — | `namespace/name` of the prompt |
| `ref` | ❌ | `"latest"` | Version ref to render |
| `variables` | ❌ | `{}` | Variable values to inject |

**Rendering rules:**

1. Retrieve the version at the given ref
2. For each `{{name}}` placeholder in the content:
   - Use the value from `variables` if provided
   - Fall back to the variable's `default` from the schema
   - If `required: true` and no value or default is available → **422 error**
3. Return the fully rendered content string

**Response `200`** — `RenderResponse`

```json
{
  "content": "You are a senior code reviewer specialising in TypeScript.\nReview for correctness and idiomatic style.",
  "slug": "osteck/code-reviewer",
  "ref": "v1.1",
  "sha": "a3f1d2e4..."
}
```

**Response `403`** — Proprietary namespace requires certificate
**Response `404`** — Prompt or ref not found
**Response `422`** — Missing required variable or invalid slug format

---

## 16. Resolve

Resolve a `cantica://` URI to a concrete `Version`. Supports both local and remote (federated) resolution.

---

### `POST /v1/resolve`

**Request body**

```json
{
  "uri": "cantica://osteck/code-reviewer@v1.1",
  "remote_url": null
}
```

| Field | Required | Description |
|---|---|---|
| `uri` | ✅ | `cantica://namespace/name@ref` URI |
| `remote_url` | ❌ | HTTP base URL of a remote Cantica instance to resolve against |

**URI format:**

```
cantica://  {namespace} / {name} @ {ref}
            osteck         code-reviewer   v1.1
            community      senior-arch     latest
            osteck         my-prompt       abc123f
```

**Response `200`** — `VersionResponse`
**Response `404`** — Prompt or ref not found
**Response `422`** — Malformed URI
**Response `502`** — Remote unreachable (when `remote_url` is set)

---

## 17. Webhooks

Webhooks deliver signed HTTP POST payloads to a configured URL when events occur.

---

### `POST /v1/hooks`

Register a new webhook.

**Request body**

```json
{
  "url": "https://my-service.example.com/cantica-hook",
  "events": ["version.created"],
  "secret": "my-hmac-signing-secret",
  "namespace": "osteck"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `url` | ✅ | — | HTTPS endpoint to POST to |
| `events` | ❌ | `["version.created"]` | List of event types |
| `secret` | ✅ | — | Used to sign the payload with HMAC-SHA256 |
| `namespace` | ❌ | `null` | Scope to a specific namespace (null = all namespaces) |

**Response `201`** — `WebhookResponse`

```json
{
  "id": "w1x2y3z4-...",
  "url": "https://my-service.example.com/cantica-hook",
  "events": ["version.created"],
  "namespace": "osteck",
  "created_at": "2026-05-24T15:00:00Z"
}
```

**Payload format** (sent to your URL on events):

```json
{
  "event": "version.created",
  "sha": "a3f1d2e4...",
  "prompt_slug": "osteck/code-reviewer",
  "author": "osteck",
  "message": "add language variable",
  "created_at": "2026-05-24T15:00:00Z"
}
```

The request includes the header:
```
X-Cantica-Signature: sha256=<hmac-hex>
```

Verify it with: `HMAC-SHA256(secret, raw_body)`.

---

### `GET /v1/hooks`

List all registered webhooks.

**Response `200`** — `WebhookResponse[]`

---

### `DELETE /v1/hooks/{hook_id}`

Delete a webhook by its ID.

**Response `204`** — Deleted
**Response `404`** — Webhook not found

---

## 18. Auth tokens

API tokens are long-lived keys for authenticating requests when `CANTICA_AUTH_ENABLED=true`. Only the SHA-256 hash of each key is stored; the raw key is returned exactly once at creation.

---

### `POST /v1/tokens`

Create a new API token.

**Request body**

```json
{ "name": "my-ci-token" }
```

**Response `201`** — `TokenResponse`

```json
{
  "id": "t1u2v3w4-...",
  "name": "my-ci-token",
  "key": "cntk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "created_at": "2026-05-24T16:00:00Z"
}
```

> ⚠️ **Save the `key` value immediately.** It is never shown again. If lost, revoke this token and create a new one.

---

### `GET /v1/tokens`

List all tokens. Raw keys are never returned.

**Response `200`** — `TokenInfo[]`

```json
[
  {
    "id": "t1u2v3w4-...",
    "name": "my-ci-token",
    "created_at": "2026-05-24T16:00:00Z",
    "last_used_at": "2026-05-24T17:45:00Z"
  }
]
```

---

### `DELETE /v1/tokens/{token_id}`

Revoke a token by its ID. The token is immediately invalid.

**Response `204`** — Revoked
**Response `404`** — Token not found

---

## 19. Error reference

All errors follow a consistent JSON envelope:

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning | Common causes |
|---|---|---|
| `400` | Bad Request | Malformed JSON body |
| `401` | Unauthorized | Missing or invalid `X-API-Key` (when auth is enabled) |
| `403` | Forbidden | Proprietary namespace accessed without a valid `X-Cantica-Certificate`; revoked certificate; publishing proprietary namespace without certificate |
| `404` | Not Found | Prompt, version, branch, tag, collection, namespace, certificate, or webhook does not exist |
| `409` | Conflict | Duplicate name (prompt, collection); SHA conflict on import; nothing to merge; certificate issued for non-proprietary namespace |
| `422` | Unprocessable | Invalid slug format; missing required render variable; malformed URI |
| `502` | Bad Gateway | Remote Cantica instance unreachable (resolve with `remote_url`) |

---

## 20. Swagger UI guide

Cantica ships with two interactive API explorers.

### Swagger UI — `/docs`

```
http://localhost:8042/docs
```

The Swagger UI lets you execute live API calls directly from the browser.

**Workflow:**

1. **Open** `http://localhost:8042/docs`
2. **Authenticate** (if auth is enabled):
   - Click the **Authorize** 🔒 button at the top right
   - Paste your API key into the `X-API-Key` input
   - Click **Authorize**, then **Close**
3. **Find an endpoint** — endpoints are grouped by tag (Namespaces, Prompts, Versions, Branches, etc.)
4. **Click the endpoint** to expand it
5. Click **Try it out** to enable the input fields
6. Fill in path parameters, query parameters, and the request body
7. Click **Execute** — the UI sends the request and shows the full response (status, headers, body)

### ReDoc — `/redoc`

```
http://localhost:8042/redoc
```

ReDoc renders a clean, read-only reference with the full schema for every request and response. No live execution — use Swagger UI for that.

### OpenAPI schema

The raw OpenAPI 3.1 JSON schema is available at:

```
http://localhost:8042/openapi.json
```

You can import this into Postman, Insomnia, or any other API client:
- **Postman:** File → Import → Link → paste the URL
- **Insomnia:** Application → Import/Export → Import Data → From URL

---

*Generated from `cantica-api` v0.1.0 — [github.com/oliben67/cantica-api](https://github.com/oliben67/cantica-api)*
