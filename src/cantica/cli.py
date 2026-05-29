"""
Typer-based command-line interface for Cantica.

The ``cantica`` CLI exposes the full feature set of the prompt registry as
terminal commands.  Each command maps directly to one or more ``VersionStore``
methods, keeping the CLI thin (input parsing, output formatting) with no
business logic of its own.

Commands
--------
serve           Start the Uvicorn development server.
mcp             Start the Cantica MCP server on stdio for use with AI agents.

new             Create a new prompt in the local vault.
commit          Save a new version; content from ``--file`` or stdin.
show            Display a prompt at an optional ref (default: latest).
log             Print the version history for a branch.
diff            Show a unified diff between two refs.
render          Render prompt content with ``{{variable}}`` substitution.
tag             Attach a named tag to a specific version SHA.
branch          List existing branches or create a new one.
fork            Deep-copy a prompt to a new namespace/name, preserving history.
rollback        Reset a branch head to a past ref.
merge           Fast-forward merge one branch into another.
push            Push a prompt and its history to a remote Cantica instance.
pull            Pull a prompt and its history from a remote Cantica instance.
list            List prompts, with optional filters (namespace, tag, model, visibility).
search          Full-text search across names, descriptions, tags, and model hints.
namespace-new   Create a namespace (optionally proprietary or encoded).
namespace-list  List all namespaces in the local vault.
cert-issue      Issue an access certificate for a proprietary namespace.
cert-list       List access certificates for a namespace.
cert-revoke     Revoke an access certificate immediately.
star / unstar   Star or remove a star from a prompt.
comment         Post a comment, optionally pinned to a specific version SHA.
collections     List collections in the local vault.
lock            Resolve ``cantica://`` URIs to exact SHAs and write a TOML lock file.
install         Fetch all versions pinned in a ``cantica.lock`` file into the local vault.

All commands accept ``--vault <path>`` to override the default vault location
(``CANTICA_VAULT_PATH`` or ``~/.cantica/vault``).
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

# Third party imports:
import httpx
import typer
import uvicorn

# Local imports:
from cantica.config import get_settings
from cantica.core.resolver import parse_address
from cantica.models import VariableSchema, Visibility
from cantica.services.lock_file import LockEntry, LockFile, read_lock, write_lock
from cantica.services.template_engine import TemplateEngine
from cantica.services.version_store import VersionStore


def _stdin_is_tty() -> bool:
    """Return ``True`` when stdin is an interactive terminal."""
    return sys.stdin.isatty()


app = typer.Typer(
    name="cantica",
    help="Cantica — versioned prompt registry.",
    no_args_is_help=True,
)


def _store(vault: Path | None = None) -> VersionStore:
    """Open and return a ``VersionStore`` for the given (or default) vault path."""
    path = vault or get_settings().vault_path
    path.mkdir(parents=True, exist_ok=True)
    return VersionStore(path)


# --------------------------------------------------------------------------- #
# serve                                                                        #
# --------------------------------------------------------------------------- #


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8042, help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
) -> None:
    """Start the Cantica API server."""
    uvicorn.run("cantica.main:app", host=host, port=port, reload=reload)


@app.command(name="mcp")
def mcp_serve() -> None:
    """Start the Cantica MCP server on stdio for use with AI agents."""
    # Local imports:
    from cantica.mcp import server as _mcp_server  # noqa: PLC0415

    _mcp_server.mcp.run("stdio")


# --------------------------------------------------------------------------- #
# new                                                                          #
# --------------------------------------------------------------------------- #


@app.command()
def new(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    description: str = typer.Option("", "-d", "--description"),
    vault: Path | None = typer.Option(None, "--vault", help="Vault path override"),
) -> None:
    """Create a new prompt in the local vault."""
    addr = parse_address(slug)
    store = _store(vault)
    if store.get_prompt(addr.namespace, addr.name):
        typer.echo(f"Error: {slug} already exists", err=True)
        raise typer.Exit(1)
    prompt = store.create_prompt(addr.namespace, addr.name, description)
    typer.echo(f"Created {prompt.slug} ({prompt.id})")


# --------------------------------------------------------------------------- #
# commit                                                                       #
# --------------------------------------------------------------------------- #


@app.command()
def commit(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    message: str = typer.Option(..., "-m", "--message", help="Commit message"),
    branch: str = typer.Option("main", "-b", "--branch"),
    file: Path | None = typer.Option(None, "-f", "--file", help="Read content from file"),
    author: str = typer.Option("", "--author", help="Author (defaults to namespace)"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Save a new version of a prompt. Content is read from --file or stdin."""
    addr = parse_address(slug)
    store = _store(vault)
    prompt = store.get_prompt(addr.namespace, addr.name)
    if not prompt:
        typer.echo(f"Error: prompt {slug} not found — run 'cantica new {slug}' first", err=True)
        raise typer.Exit(1)

    if file:
        content = file.read_text()
    elif not _stdin_is_tty():
        content = sys.stdin.read()
    else:
        typer.echo("Error: provide content via --file or stdin", err=True)
        raise typer.Exit(1)

    version = store.commit(
        prompt.id,
        content,
        message,
        author=author or addr.namespace,
        branch=branch,
    )
    typer.echo(f"[{branch}] {version.sha[:7]}  {message}")


# --------------------------------------------------------------------------- #
# show                                                                         #
# --------------------------------------------------------------------------- #


@app.command()
def show(
    address: Annotated[str, typer.Argument(help="namespace/name[@ref]")],
    raw: bool = typer.Option(False, "--raw", help="Print only the prompt content"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Display a prompt at a given ref (default: latest)."""
    addr = parse_address(address)
    store = _store(vault)
    try:
        version = store.resolve(addr.namespace, addr.name, addr.ref)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if raw:
        typer.echo(version.content)
        return

    typer.echo(f"prompt:  {addr.namespace}/{addr.name}")
    typer.echo(f"sha:     {version.sha[:7]}  ({version.sha})")
    typer.echo(f"branch:  {version.branch}")
    typer.echo(f"author:  {version.author}")
    typer.echo(f"date:    {version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if version.tags:
        typer.echo(f"tags:    {', '.join(version.tags)}")
    typer.echo(f"message: {version.message}")
    typer.echo("")
    typer.echo(version.content)


# --------------------------------------------------------------------------- #
# log                                                                          #
# --------------------------------------------------------------------------- #


@app.command()
def log(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    branch: str = typer.Option("main", "-b", "--branch"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Show version history for a prompt."""
    addr = parse_address(slug)
    store = _store(vault)
    prompt = store.get_prompt(addr.namespace, addr.name)
    if not prompt:
        typer.echo(f"Error: prompt {slug} not found", err=True)
        raise typer.Exit(1)

    versions = store.log(prompt.id, branch)
    if not versions:
        typer.echo("No commits yet.")
        return

    for v in versions:
        tag_str = f"  ({', '.join(v.tags)})" if v.tags else ""
        typer.echo(
            f"{v.sha[:7]}  {v.created_at.strftime('%Y-%m-%d %H:%M')}  "
            f"{v.author}  {v.message}{tag_str}"
        )


# --------------------------------------------------------------------------- #
# diff                                                                         #
# --------------------------------------------------------------------------- #


@app.command()
def diff(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    ref1: Annotated[str, typer.Argument(help="First ref (SHA, tag, or branch)")],
    ref2: Annotated[str, typer.Argument(help="Second ref")],
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Show a unified diff between two refs."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        v1 = store.resolve(addr.namespace, addr.name, ref1)
        v2 = store.resolve(addr.namespace, addr.name, ref2)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    result = store.diff(v1.sha, v2.sha)
    if result:
        typer.echo(result, nl=False)
    else:
        typer.echo("No differences.")


# --------------------------------------------------------------------------- #
# render                                                                       #
# --------------------------------------------------------------------------- #


@app.command()
def render(
    address: Annotated[str, typer.Argument(help="namespace/name[@ref]")],
    var: Annotated[list[str] | None, typer.Option("--var", help="key=value")] = None,
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Render a prompt with variable substitution."""
    addr = parse_address(address)
    store = _store(vault)
    try:
        version = store.resolve(addr.namespace, addr.name, addr.ref)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    variables: dict[str, str] = {}
    for pair in var or []:
        if "=" not in pair:
            typer.echo(f"Error: --var must be key=value, got {pair!r}", err=True)
            raise typer.Exit(1)
        k, v = pair.split("=", 1)
        variables[k] = v

    engine = TemplateEngine()
    try:
        content = engine.render_with_defaults(version.content, version.variables, variables)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(content)


# --------------------------------------------------------------------------- #
# tag                                                                          #
# --------------------------------------------------------------------------- #


@app.command()
def tag(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    tag_name: Annotated[str, typer.Argument(help="Tag name (e.g. v1.0)")],
    ref: str = typer.Option("latest", "--ref", help="Ref to tag"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Tag a specific version of a prompt."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        version = store.resolve(addr.namespace, addr.name, ref)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    store.create_tag(store.get_prompt(addr.namespace, addr.name).id, tag_name, version.sha)  # type: ignore[union-attr]
    typer.echo(f"Tagged {version.sha[:7]} as {tag_name!r}")


# --------------------------------------------------------------------------- #
# branch                                                                      #
# --------------------------------------------------------------------------- #


@app.command()
def branch(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    branch_name: Annotated[str | None, typer.Argument(help="New branch name")] = None,
    from_ref: str = typer.Option("latest", "--from", help="Ref to branch from"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """List branches, or create a new one at a given ref."""
    addr = parse_address(slug)
    store = _store(vault)
    prompt = store.get_prompt(addr.namespace, addr.name)
    if not prompt:
        typer.echo(f"Error: prompt {slug} not found", err=True)
        raise typer.Exit(1)

    if branch_name is None:
        branches = store.list_branches(prompt.id)
        for b in branches:
            marker = "*" if b.name == prompt.default_branch else " "
            typer.echo(f"{marker} {b.name}  ({b.head_sha[:7]})")
        return

    try:
        version = store.resolve(addr.namespace, addr.name, from_ref)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    b = store.create_branch(prompt.id, branch_name, version.sha)
    typer.echo(f"Branch {b.name!r} created at {version.sha[:7]}")


# --------------------------------------------------------------------------- #
# fork                                                                        #
# --------------------------------------------------------------------------- #


@app.command()
def fork(
    source: Annotated[str, typer.Argument(help="Source namespace/name")],
    dest: Annotated[str, typer.Argument(help="Destination namespace/name")],
    from_branch: str = typer.Option("main", "--branch", "-b", help="Branch to fork from"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Fork a prompt into a new namespace/name, preserving full history."""
    src = parse_address(source)
    dst = parse_address(dest)
    store = _store(vault)
    try:
        fork_record = store.fork(src.namespace, src.name, dst.namespace, dst.name, from_branch)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Forked {fork_record.source_slug} → {fork_record.fork_slug}")


# --------------------------------------------------------------------------- #
# rollback                                                                    #
# --------------------------------------------------------------------------- #


@app.command()
def rollback(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    ref: Annotated[str, typer.Argument(help="SHA, tag, or branch to roll back to")],
    branch_name: str = typer.Option("main", "--branch", "-b"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Reset a branch head to a past ref."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        version = store.rollback(addr.namespace, addr.name, ref, branch_name)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Branch {branch_name!r} reset to {version.sha[:7]}  {version.message}")


# --------------------------------------------------------------------------- #
# merge                                                                       #
# --------------------------------------------------------------------------- #


@app.command()
def merge(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    from_branch: str = typer.Option(..., "--from", help="Branch to merge from"),
    into_branch: str = typer.Option("main", "--into"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Fast-forward merge one branch into another."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        version = store.merge(addr.namespace, addr.name, from_branch, into_branch)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Merged {from_branch!r} → {into_branch!r} at {version.sha[:7]}")


# --------------------------------------------------------------------------- #
# push                                                                        #
# --------------------------------------------------------------------------- #


@app.command()
def push(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    remote: str = typer.Option("", "--remote", "-r", help="Remote Cantica base URL"),
    api_key: str | None = typer.Option(None, "--api-key", help="Remote API key"),
    certificate: str | None = typer.Option(
        None, "--certificate", "-c", help="Certificate token for proprietary remote namespace"
    ),
    branch: str = typer.Option("main", "-b", "--branch"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Push a prompt and its full history to a remote Cantica instance."""
    addr = parse_address(slug)
    store = _store(vault)

    remote_url = remote or get_settings().remote_url
    if not remote_url:
        typer.echo("Error: --remote URL is required (or set CANTICA_REMOTE_URL)", err=True)
        raise typer.Exit(1)

    prompt = store.get_prompt(addr.namespace, addr.name)
    if not prompt:
        typer.echo(f"Error: prompt {slug} not found", err=True)
        raise typer.Exit(1)

    versions = list(reversed(store.log(prompt.id, branch)))  # oldest first
    tags = store.list_tags(prompt.id)

    headers: dict[str, str] = {"X-API-Key": api_key} if api_key else {}
    if certificate:
        headers["X-Cantica-Certificate"] = certificate
    with httpx.Client(base_url=remote_url, headers=headers, timeout=30.0) as client:
        r = client.get(f"/v1/prompts/{addr.namespace}/{addr.name}")
        if r.status_code == 404:
            r = client.post(
                "/v1/prompts",
                json={
                    "namespace": addr.namespace,
                    "name": addr.name,
                    "description": prompt.description,
                    "tags": prompt.tags,
                    "model_hints": prompt.model_hints,
                    "license": prompt.license,
                    "visibility": prompt.visibility.value,
                    "variables": [v.model_dump() for v in prompt.variables],
                },
            )
            r.raise_for_status()
            typer.echo(f"Created {slug} on remote.")

        r = client.get(
            f"/v1/prompts/{addr.namespace}/{addr.name}/versions",
            params={"branch": branch},
        )
        r.raise_for_status()
        remote_shas = {v["sha"] for v in r.json()}

        pushed = 0
        for v in versions:
            if v.sha in remote_shas:
                continue
            r = client.post(
                f"/v1/prompts/{addr.namespace}/{addr.name}/versions",
                json={
                    "content": v.content,
                    "message": v.message,
                    "author": v.author,
                    "branch": branch,
                    "variables": [var.model_dump() for var in v.variables],
                    "sha": v.sha,
                    "parent_sha": v.parent_sha,
                    "created_at": v.created_at.isoformat(),
                },
            )
            r.raise_for_status()
            pushed += 1
            typer.echo(f"  {v.sha[:7]}  {v.message}")

        r = client.get(f"/v1/prompts/{addr.namespace}/{addr.name}/tags")
        r.raise_for_status()
        remote_tag_names = {t["name"] for t in r.json()}
        for t in tags:
            if t.name not in remote_tag_names:
                client.post(
                    f"/v1/prompts/{addr.namespace}/{addr.name}/tags",
                    json={"name": t.name, "sha": t.sha},
                ).raise_for_status()
                typer.echo(f"  tag {t.name!r} → {t.sha[:7]}")

    if pushed == 0:
        typer.echo("Already up to date.")
    else:
        typer.echo(f"Pushed {pushed} version(s) to {remote_url}")


# --------------------------------------------------------------------------- #
# pull                                                                        #
# --------------------------------------------------------------------------- #


@app.command()
def pull(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    remote: str = typer.Option("", "--remote", "-r", help="Remote Cantica base URL"),
    api_key: str | None = typer.Option(None, "--api-key", help="Remote API key"),
    certificate: str | None = typer.Option(
        None, "--certificate", "-c", help="Certificate token for proprietary remote namespace"
    ),
    branch: str = typer.Option("main", "-b", "--branch"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Pull a prompt and its full history from a remote Cantica instance."""
    addr = parse_address(slug)
    store = _store(vault)

    remote_url = remote or get_settings().remote_url
    if not remote_url:
        typer.echo("Error: --remote URL is required (or set CANTICA_REMOTE_URL)", err=True)
        raise typer.Exit(1)

    headers: dict[str, str] = {"X-API-Key": api_key} if api_key else {}
    if certificate:
        headers["X-Cantica-Certificate"] = certificate
    with httpx.Client(base_url=remote_url, headers=headers, timeout=30.0) as client:
        r = client.get(f"/v1/prompts/{addr.namespace}/{addr.name}")
        if r.status_code == 404:
            typer.echo(f"Error: {slug} not found on remote", err=True)
            raise typer.Exit(1)
        r.raise_for_status()
        remote_prompt = r.json()

        r = client.get(
            f"/v1/prompts/{addr.namespace}/{addr.name}/versions",
            params={"branch": branch},
        )
        r.raise_for_status()
        remote_versions = list(reversed(r.json()))  # oldest first

        r = client.get(f"/v1/prompts/{addr.namespace}/{addr.name}/tags")
        r.raise_for_status()
        remote_tags = r.json()

    prompt = store.get_prompt(addr.namespace, addr.name)
    if not prompt:
        prompt = store.create_prompt(
            addr.namespace,
            addr.name,
            description=remote_prompt.get("description", ""),
            tags=remote_prompt.get("tags", []),
            model_hints=remote_prompt.get("model_hints", []),
            license=remote_prompt.get("license", "MIT"),
            visibility=Visibility(remote_prompt.get("visibility", "public")),
            variables=[VariableSchema(**v) for v in remote_prompt.get("variables", [])],
        )
        typer.echo(f"Created {slug} locally.")

    pulled = 0
    for rv in remote_versions:
        if store.has_version(rv["sha"]):
            continue
        store.import_version(
            prompt.id,
            rv["sha"],
            rv["content"],
            rv["message"],
            rv["author"],
            branch,
            rv.get("parent_sha"),
            datetime.fromisoformat(rv["created_at"]),
            [VariableSchema(**v) for v in rv.get("variables", [])],
        )
        pulled += 1
        typer.echo(f"  {rv['sha'][:7]}  {rv['message']}")

    for rt in remote_tags:
        if store.has_version(rt["sha"]):
            try:
                store.create_tag(prompt.id, rt["name"], rt["sha"])
                typer.echo(f"  tag {rt['name']!r} → {rt['sha'][:7]}")
            except Exception:  # pragma: no cover
                pass  # tag already exists

    if pulled == 0:
        typer.echo("Already up to date.")
    else:
        typer.echo(f"Pulled {pulled} version(s) from {remote_url}")


# --------------------------------------------------------------------------- #
# list                                                                        #
# --------------------------------------------------------------------------- #


@app.command(name="list")
def list_prompts_cmd(
    namespace: str | None = typer.Option(None, "--namespace", "-n", help="Filter by namespace"),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag"),
    model: str | None = typer.Option(None, "--model", help="Filter by model hint"),
    visibility: str | None = typer.Option(None, "--visibility", help="Filter by visibility"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """List prompts in the local vault, with optional filters."""
    store = _store(vault)
    prompts = store.list_prompts(namespace, tag=tag, model=model, visibility=visibility)
    store.close()
    if not prompts:
        typer.echo("No prompts found.")
        return
    for p in prompts:
        desc = f"  {p.description}" if p.description else ""
        typer.echo(f"{p.slug}{desc}")


# --------------------------------------------------------------------------- #
# search                                                                      #
# --------------------------------------------------------------------------- #


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Full-text search query")],
    namespace: str | None = typer.Option(None, "--namespace", "-n", help="Filter by namespace"),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag"),
    model: str | None = typer.Option(None, "--model", help="Filter by model hint"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Full-text search across prompt names, descriptions, tags, and model hints."""
    store = _store(vault)
    results = store.search_prompts(query, namespace=namespace, tag=tag, model=model)
    store.close()
    if not results:
        typer.echo("No results found.")
        return
    for p in results:
        desc = f"  {p.description}" if p.description else ""
        typer.echo(f"{p.slug}{desc}")


# --------------------------------------------------------------------------- #
# namespace management                                                        #
# --------------------------------------------------------------------------- #


@app.command(name="namespace-new")
def namespace_new(
    name: Annotated[str, typer.Argument(help="Namespace name")],
    description: str = typer.Option("", "-d", "--description"),
    proprietary: bool = typer.Option(
        False, "--proprietary", help="Restrict access with certificates"
    ),
    encoded: bool = typer.Option(False, "--encoded", help="Encrypt content at rest (AES-256-GCM)"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Create a namespace in the local vault."""
    store = _store(vault)
    ns = store.create_namespace(
        name,
        description=description,
        is_proprietary=proprietary,
        encoded=encoded,
    )
    store.close()
    flags = []
    if ns.is_proprietary:
        flags.append("proprietary")
    if ns.encoded:
        flags.append("encoded")
    suffix = f"  [{', '.join(flags)}]" if flags else ""
    typer.echo(f"Created namespace {ns.name}{suffix}")


@app.command(name="namespace-list")
def namespace_list(
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """List all namespaces in the local vault."""
    store = _store(vault)
    namespaces = store.list_namespaces()
    store.close()
    if not namespaces:
        typer.echo("No namespaces found.")
        return
    for ns in namespaces:
        flags = []
        if ns.is_proprietary:
            flags.append("proprietary")
        if ns.encoded:
            flags.append("encoded")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        desc = f"  {ns.description}" if ns.description else ""
        typer.echo(f"{ns.name}{desc}{suffix}")


# --------------------------------------------------------------------------- #
# certificate management                                                      #
# --------------------------------------------------------------------------- #


@app.command(name="cert-issue")
def cert_issue(
    namespace: Annotated[str, typer.Argument(help="Namespace name")],
    granted_to: str = typer.Option(..., "--to", help="Grantee identifier"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Issue a new access certificate for a proprietary namespace."""
    store = _store(vault)
    try:
        cert = store.issue_certificate(namespace, granted_to)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    store.close()
    typer.echo(f"Certificate issued for {namespace!r} → {granted_to!r}")
    typer.echo(f"  ID:    {cert.id}")
    typer.echo(f"  Token: {cert.token}")
    typer.echo("")
    typer.echo("Save the token — it will not be shown again.")


@app.command(name="cert-list")
def cert_list(
    namespace: Annotated[str, typer.Argument(help="Namespace name")],
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """List access certificates for a namespace."""
    store = _store(vault)
    if store.get_namespace(namespace) is None:
        store.close()
        typer.echo(f"Error: namespace {namespace!r} not found", err=True)
        raise typer.Exit(1)
    certs = store.list_certificates(namespace)
    store.close()
    if not certs:
        typer.echo("No certificates found.")
        return
    for c in certs:
        revoked = "  [REVOKED]" if c.revoked else ""
        expires = f"  expires {c.expires_at}" if c.expires_at else ""
        typer.echo(f"{c.id}  →  {c.granted_to}{expires}{revoked}")


@app.command(name="cert-revoke")
def cert_revoke(
    cert_id: Annotated[str, typer.Argument(help="Certificate ID")],
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Revoke an access certificate immediately."""
    store = _store(vault)
    found = store.revoke_certificate(cert_id)
    store.close()
    if not found:
        typer.echo(f"Error: certificate {cert_id!r} not found", err=True)
        raise typer.Exit(1)
    typer.echo(f"Revoked certificate {cert_id}")


# --------------------------------------------------------------------------- #
# star / unstar                                                               #
# --------------------------------------------------------------------------- #


@app.command()
def star(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    actor: str = typer.Option("local", "--as", help="Actor namespace"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Star a prompt."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        store.star_prompt(addr.namespace, addr.name, actor)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    store.close()
    typer.echo(f"Starred {slug}")


@app.command()
def unstar(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    actor: str = typer.Option("local", "--as", help="Actor namespace"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Unstar a prompt."""
    addr = parse_address(slug)
    store = _store(vault)
    try:
        removed = store.unstar_prompt(addr.namespace, addr.name, actor)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    store.close()
    if removed:
        typer.echo(f"Unstarred {slug}")
    else:
        typer.echo(f"{slug} was not starred by {actor}")


# --------------------------------------------------------------------------- #
# comment                                                                      #
# --------------------------------------------------------------------------- #


@app.command()
def comment(
    slug: Annotated[str, typer.Argument(help="namespace/name")],
    body: Annotated[str, typer.Argument(help="Comment text")],
    author: str = typer.Option("local", "--author", help="Author name"),
    ref: str | None = typer.Option(None, "--ref", help="Pin comment to a specific ref"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Add a comment to a prompt."""
    addr = parse_address(slug)
    store = _store(vault)
    version_sha: str | None = None
    if ref:
        try:
            v = store.resolve(addr.namespace, addr.name, ref)
            version_sha = v.sha
        except KeyError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
    try:
        c = store.add_comment(addr.namespace, addr.name, body, author, version_sha)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    store.close()
    typer.echo(f"Comment {c.id[:8]} added to {slug}")


# --------------------------------------------------------------------------- #
# collections                                                                  #
# --------------------------------------------------------------------------- #


@app.command(name="collections")
def list_collections_cmd(
    namespace: str | None = typer.Option(None, "--namespace", "-n"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """List collections."""
    store = _store(vault)
    colls = store.list_collections(namespace)
    store.close()
    if not colls:
        typer.echo("No collections found.")
        return
    for c in colls:
        desc = f"  {c.description}" if c.description else ""
        typer.echo(f"{c.namespace}/{c.name}{desc}")


# --------------------------------------------------------------------------- #
# lock                                                                         #
# --------------------------------------------------------------------------- #


@app.command(name="lock")
def lock_cmd(
    uris: Annotated[list[str], typer.Argument(help="cantica:// URIs to lock")],
    output: Path = typer.Option(Path("cantica.lock"), "--output", "-o", help="Lock file path"),
    remote_url: str | None = typer.Option(
        None, "--remote", help="Override remote base URL for URIs with a host"
    ),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Resolve cantica:// URIs to specific SHAs and write a lock file."""
    store = _store(vault)
    entries: list[LockEntry] = []
    errors = 0
    for uri in uris:
        try:
            version = store.resolve_uri(uri, remote_url)
        except (KeyError, ValueError, ConnectionError) as exc:
            typer.echo(f"Error resolving {uri}: {exc}", err=True)
            errors += 1
            continue
        addr = parse_address(uri)
        entries.append(
            LockEntry(
                uri=uri,
                namespace=addr.namespace,
                name=addr.name,
                ref=addr.ref,
                sha=version.sha,
                locked_at=datetime.now(UTC),
            )
        )
        typer.echo(f"  {uri} → {version.sha[:7]}")
    store.close()
    if errors:
        raise typer.Exit(1)
    lock = LockFile(generated_at=datetime.now(UTC), prompts=entries)
    write_lock(lock, output)
    typer.echo(f"Wrote {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} to {output}")


# --------------------------------------------------------------------------- #
# install                                                                      #
# --------------------------------------------------------------------------- #


@app.command(name="install")
def install_cmd(
    lock_file: Path = typer.Option(
        Path("cantica.lock"), "--lock-file", "-l", help="Lock file to read"
    ),
    remote_url: str | None = typer.Option(None, "--remote", help="Override remote base URL"),
    vault: Path | None = typer.Option(None, "--vault"),
) -> None:
    """Fetch all versions pinned in a lock file into the local vault."""
    if not lock_file.exists():
        typer.echo(f"Lock file not found: {lock_file}", err=True)
        raise typer.Exit(1)

    lock = read_lock(lock_file)
    store = _store(vault)
    fetched = 0
    for entry in lock.prompts:
        if store.get_version(entry.sha) is not None:
            typer.echo(f"  {entry.uri} already present ({entry.sha[:7]})")
            continue
        try:
            version = store.resolve_uri(entry.uri, remote_url)
        except (KeyError, ValueError, ConnectionError) as exc:
            typer.echo(f"Error fetching {entry.uri}: {exc}", err=True)
            continue
        if version.sha != entry.sha:
            typer.echo(
                f"Warning: {entry.uri} resolved to {version.sha[:7]} but lock has {entry.sha[:7]}",
                err=True,
            )
        prompt = store.get_prompt(entry.namespace, entry.name)
        if prompt is None:
            prompt = store.create_prompt(entry.namespace, entry.name)
        store.import_version(
            prompt.id,
            version.sha,
            version.content,
            version.message,
            version.author,
            version.branch,
            version.parent_sha,
            version.created_at,
        )
        fetched += 1
        typer.echo(f"  Fetched {entry.uri} ({version.sha[:7]})")
    store.close()
    typer.echo(f"Done. {fetched} version(s) fetched.")


if __name__ == "__main__":  # pragma: no cover
    app()
