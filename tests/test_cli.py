# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path
from unittest.mock import MagicMock, patch

# Third party imports:
import pytest
from typer.testing import CliRunner

# Local imports:
from cantica.cli import _stdin_is_tty, app
from cantica.models import VariableSchema
from cantica.models.prompt import Prompt, Version
from cantica.services.version_store import VersionStore

runner = CliRunner()


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _seed(vault: Path) -> tuple[VersionStore, Prompt, Version]:
    store = VersionStore(vault)
    prompt = store.create_prompt("osteck", "test")
    v1 = store.commit(prompt.id, "Hello world", "First", "osteck")
    return store, prompt, v1


# ------------------------------------------------------------------ #
# _stdin_is_tty                                                        #
# ------------------------------------------------------------------ #


def test_stdin_is_tty_returns_bool() -> None:
    result = _stdin_is_tty()
    assert isinstance(result, bool)


# ------------------------------------------------------------------ #
# serve                                                                #
# ------------------------------------------------------------------ #


def test_serve_calls_uvicorn() -> None:
    with patch("cantica.cli.uvicorn") as mock_uvicorn:
        result = runner.invoke(app, ["serve", "--port", "9999"])
    assert result.exit_code == 0
    mock_uvicorn.run.assert_called_once_with(
        "cantica.main:app", host="0.0.0.0", port=9999, reload=False
    )


def test_serve_reload_flag() -> None:
    with patch("cantica.cli.uvicorn") as mock_uvicorn:
        runner.invoke(app, ["serve", "--reload"])
    assert mock_uvicorn.run.call_args.kwargs["reload"] is True


# ------------------------------------------------------------------ #
# new                                                                  #
# ------------------------------------------------------------------ #


def test_new_creates_prompt(tmp_path: Path) -> None:
    result = runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "osteck/test" in result.output


def test_new_with_description(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["new", "osteck/test", "-d", "A fine prompt", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 0


def test_new_duplicate_exits_1(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.output


# ------------------------------------------------------------------ #
# commit                                                               #
# ------------------------------------------------------------------ #


def test_commit_from_stdin(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    result = runner.invoke(
        app,
        ["commit", "osteck/test", "-m", "First", "--vault", str(tmp_path)],
        input="Hello world",
    )
    assert result.exit_code == 0
    assert "First" in result.output


def test_commit_from_file(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    content_file = tmp_path / "prompt.txt"
    content_file.write_text("From file content")
    result = runner.invoke(
        app,
        [
            "commit",
            "osteck/test",
            "-m",
            "From file",
            "-f",
            str(content_file),
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_commit_with_author(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    result = runner.invoke(
        app,
        ["commit", "osteck/test", "-m", "Authored", "--author", "alice", "--vault", str(tmp_path)],
        input="content",
    )
    assert result.exit_code == 0


def test_commit_with_branch(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    runner.invoke(
        app, ["commit", "osteck/test", "-m", "First", "--vault", str(tmp_path)], input="v1"
    )
    result = runner.invoke(
        app,
        ["commit", "osteck/test", "-m", "Feature", "-b", "feature", "--vault", str(tmp_path)],
        input="feature content",
    )
    assert result.exit_code == 0
    assert "feature" in result.output


def test_commit_missing_prompt_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["commit", "osteck/missing", "-m", "msg", "--vault", str(tmp_path)],
        input="content",
    )
    assert result.exit_code == 1
    assert "not found" in result.output


def test_commit_no_content_exits_1(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    with patch("cantica.cli._stdin_is_tty", return_value=True):
        result = runner.invoke(
            app, ["commit", "osteck/test", "-m", "msg", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 1
    assert "provide content" in result.output


# ------------------------------------------------------------------ #
# show                                                                 #
# ------------------------------------------------------------------ #


def test_show_latest(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    result = runner.invoke(app, ["show", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Hello world" in result.output
    assert v1.sha[:7] in result.output


def test_show_raw(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["show", "osteck/test", "--raw", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output.strip() == "Hello world"


def test_show_with_tags_in_output(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.create_tag(prompt.id, "v1.0", v1.sha)
    result = runner.invoke(app, ["show", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "v1.0" in result.output


def test_show_at_ref(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    result = runner.invoke(app, ["show", f"osteck/test@{v1.sha[:7]}", "--vault", str(tmp_path)])
    assert result.exit_code == 0


def test_show_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["show", "osteck/missing", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# log                                                                  #
# ------------------------------------------------------------------ #


def test_log_shows_history(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.commit(prompt.id, "Hello Python", "Second", "osteck")
    result = runner.invoke(app, ["log", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "First" in result.output
    assert "Second" in result.output


def test_log_shows_tags(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.create_tag(prompt.id, "v1.0", v1.sha)
    result = runner.invoke(app, ["log", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "v1.0" in result.output


def test_log_no_commits(tmp_path: Path) -> None:
    runner.invoke(app, ["new", "osteck/test", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["log", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No commits" in result.output


def test_log_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["log", "osteck/missing", "--vault", str(tmp_path)])
    assert result.exit_code == 1


def test_log_branch_flag(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.create_branch(prompt.id, "feature", v1.sha)
    store.commit(prompt.id, "Feature work", "Feature commit", "osteck", branch="feature")
    result = runner.invoke(app, ["log", "osteck/test", "-b", "feature", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Feature commit" in result.output


# ------------------------------------------------------------------ #
# diff                                                                 #
# ------------------------------------------------------------------ #


def test_diff_shows_changes(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    v2 = store.commit(prompt.id, "Hello Python", "Second", "osteck")
    result = runner.invoke(
        app,
        [
            "diff",
            "osteck/test",
            v1.sha[:7],
            v2.sha[:7],
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "-Hello world" in result.output
    assert "+Hello Python" in result.output


def test_diff_no_changes(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    result = runner.invoke(
        app,
        [
            "diff",
            "osteck/test",
            v1.sha[:7],
            v1.sha[:7],
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "No differences" in result.output


def test_diff_bad_ref_exits_1(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(
        app,
        [
            "diff",
            "osteck/test",
            "latest",
            "nonexistent",
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# render                                                               #
# ------------------------------------------------------------------ #


def test_render_with_var(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    prompt = store.create_prompt("osteck", "greeter")
    store.commit(
        prompt.id,
        "Hello {{name}}!",
        "First",
        "osteck",
        variables=[VariableSchema(name="name", required=True)],
    )
    result = runner.invoke(
        app,
        [
            "render",
            "osteck/greeter",
            "--var",
            "name=World",
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Hello World!" in result.output


def test_render_uses_defaults(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    prompt = store.create_prompt("osteck", "greeter")
    store.commit(
        prompt.id,
        "Hello {{name}}!",
        "First",
        "osteck",
        variables=[VariableSchema(name="name", default="World")],
    )
    result = runner.invoke(app, ["render", "osteck/greeter", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Hello World!" in result.output


def test_render_missing_required_exits_1(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    prompt = store.create_prompt("osteck", "greeter")
    store.commit(
        prompt.id,
        "Hello {{name}}!",
        "First",
        "osteck",
        variables=[VariableSchema(name="name", required=True)],
    )
    result = runner.invoke(app, ["render", "osteck/greeter", "--vault", str(tmp_path)])
    assert result.exit_code == 1


def test_render_bad_var_format_exits_1(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(
        app,
        [
            "render",
            "osteck/test",
            "--var",
            "noequals",
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "key=value" in result.output


def test_render_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["render", "osteck/missing", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# tag                                                                  #
# ------------------------------------------------------------------ #


def test_tag_command(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["tag", "osteck/test", "v1.0", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "v1.0" in result.output


def test_tag_with_explicit_ref(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    result = runner.invoke(
        app,
        [
            "tag",
            "osteck/test",
            "v1.0",
            "--ref",
            v1.sha[:7],
            "--vault",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_tag_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["tag", "osteck/missing", "v1.0", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# branch                                                               #
# ------------------------------------------------------------------ #


def test_branch_lists_branches(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["branch", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "main" in result.output


def test_branch_creates_branch(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["branch", "osteck/test", "feature", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "feature" in result.output


def test_branch_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["branch", "osteck/missing", "--vault", str(tmp_path)])
    assert result.exit_code == 1


def test_branch_bad_ref_exits_1(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(
        app,
        ["branch", "osteck/test", "feature", "--from", "nonexistent", "--vault", str(tmp_path)],
    )
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# fork                                                                 #
# ------------------------------------------------------------------ #


def test_fork_creates_fork(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["fork", "osteck/test", "alice/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "osteck/test" in result.output
    assert "alice/test" in result.output


def test_fork_source_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["fork", "osteck/missing", "alice/test", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_fork_dest_exists_exits_1(tmp_path: Path) -> None:
    _seed(tmp_path)
    runner.invoke(app, ["fork", "osteck/test", "alice/test", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["fork", "osteck/test", "alice/test", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.output


# ------------------------------------------------------------------ #
# rollback                                                             #
# ------------------------------------------------------------------ #


def test_rollback_resets_branch(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.commit(prompt.id, "v2", "Second", "osteck")
    result = runner.invoke(
        app,
        ["rollback", "osteck/test", v1.sha[:7], "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert v1.sha[:7] in result.output


def test_rollback_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["rollback", "osteck/missing", "latest", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# ------------------------------------------------------------------ #
# merge                                                                #
# ------------------------------------------------------------------ #


def test_merge_fast_forwards(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    # branch from main HEAD so fast-forward is possible
    store.create_branch(prompt.id, "feature", v1.sha)
    v2 = store.commit(prompt.id, "feature work", "Feature", "osteck", branch="feature")
    # main is still at v1, feature is at v2 → fast-forward is valid
    result = runner.invoke(
        app,
        ["merge", "osteck/test", "--from", "feature", "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert v2.sha[:7] in result.output


def test_merge_not_found_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["merge", "osteck/missing", "--from", "feature", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 1


def test_merge_diverged_exits_1(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.create_branch(prompt.id, "feature", v1.sha)
    store.commit(prompt.id, "main work", "Main2", "osteck", branch="main")
    store.commit(prompt.id, "feature work", "Feature", "osteck", branch="feature")
    result = runner.invoke(
        app,
        ["merge", "osteck/test", "--from", "feature", "--vault", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "diverged" in result.output


# ------------------------------------------------------------------ #
# push / pull helpers                                                  #
# ------------------------------------------------------------------ #


def _mock_response(status: int, body=None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.raise_for_status = MagicMock()
    return r


def _mock_http_client(get_map: dict, post_map: dict) -> MagicMock:
    """Build a context-manager-compatible mock httpx.Client."""
    client = MagicMock()

    def _get(url, **_kw):
        for key, resp in get_map.items():
            if url.endswith(key):
                return resp
        return _mock_response(404)

    def _post(url, **_kw):
        for key, resp in post_map.items():
            if url.endswith(key):
                return resp
        return _mock_response(404)

    client.get.side_effect = _get
    client.post.side_effect = _post
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


# ------------------------------------------------------------------ #
# push                                                                 #
# ------------------------------------------------------------------ #


def test_push_sends_versions(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    v1_data = {
        "sha": v1.sha,
        "content": "Hello world",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(prompt.id),
    }
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, {"id": str(prompt.id)}),
            "/osteck/test/versions": _mock_response(200, []),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={
            "/osteck/test/versions": _mock_response(201, v1_data),
        },
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app, ["push", "osteck/test", "--remote", "http://remote:8042", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Pushed 1" in result.output


def test_push_creates_prompt_on_remote(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    v1_data = {
        "sha": v1.sha,
        "content": "Hello world",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(prompt.id),
    }
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(404),
            "/osteck/test/versions": _mock_response(200, []),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={
            "/v1/prompts": _mock_response(201, {"id": str(prompt.id)}),
            "/osteck/test/versions": _mock_response(201, v1_data),
        },
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app, ["push", "osteck/test", "--remote", "http://remote:8042", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Created" in result.output


def test_push_already_up_to_date(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, {}),
            "/osteck/test/versions": _mock_response(200, [{"sha": v1.sha}]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={},
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app, ["push", "osteck/test", "--remote", "http://remote:8042", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Already up to date" in result.output


def test_push_no_remote_exits_1(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["push", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "CANTICA_REMOTE_URL" in result.output


def test_push_missing_local_prompt_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["push", "osteck/missing", "--remote", "http://r:8042", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "not found" in result.output


def test_push_with_certificate(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    mock_client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, {"id": str(prompt.id)}),
            "/osteck/test/versions": _mock_response(200, [{"sha": v1.sha}]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={},
    )
    with patch("cantica.cli.httpx.Client") as mock_cls:
        mock_cls.return_value = mock_client
        result = runner.invoke(
            app,
            [
                "push", "osteck/test",
                "--remote", "http://r:8042",
                "--certificate", "cert-token-abc",
                "--vault", str(tmp_path),
            ],
        )
    assert result.exit_code == 0
    ctor_kwargs = mock_cls.call_args.kwargs
    assert ctor_kwargs["headers"].get("X-Cantica-Certificate") == "cert-token-abc"


def test_push_includes_tags(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    store.create_tag(prompt.id, "v1.0", v1.sha)
    tag_post = _mock_response(201, {})
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, {}),
            "/osteck/test/versions": _mock_response(200, [{"sha": v1.sha}]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={"/osteck/test/tags": tag_post},
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app, ["push", "osteck/test", "--remote", "http://r:8042", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "v1.0" in result.output


# ------------------------------------------------------------------ #
# pull                                                                 #
# ------------------------------------------------------------------ #


def test_pull_imports_versions(tmp_path: Path) -> None:
    # build a real version on a "remote" store so we have valid SHA data
    remote = VersionStore(tmp_path / "remote")
    r_prompt = remote.create_prompt("osteck", "test")
    r_v1 = remote.commit(r_prompt.id, "Hello world", "First", "osteck")

    v1_data = {
        "sha": r_v1.sha,
        "content": "Hello world",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": r_v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(r_prompt.id),
    }
    prompt_data = {
        "id": str(r_prompt.id),
        "namespace": "osteck",
        "name": "test",
        "description": "",
        "tags": [],
        "model_hints": [],
        "license": "MIT",
        "visibility": "public",
        "variables": [],
    }
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, prompt_data),
            "/osteck/test/versions": _mock_response(200, [v1_data]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={},
    )
    local_vault = tmp_path / "local"
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app,
            ["pull", "osteck/test", "--remote", "http://remote:8042", "--vault", str(local_vault)],
        )
    assert result.exit_code == 0
    assert "Pulled 1" in result.output
    local = VersionStore(local_vault)
    assert local.has_version(r_v1.sha)


def test_pull_already_up_to_date(tmp_path: Path) -> None:
    store, prompt, v1 = _seed(tmp_path)
    v1_data = {
        "sha": v1.sha,
        "content": "Hello world",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(prompt.id),
    }
    prompt_data = {
        "namespace": "osteck",
        "name": "test",
        "description": "",
        "tags": [],
        "model_hints": [],
        "license": "MIT",
        "visibility": "public",
        "variables": [],
    }
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, prompt_data),
            "/osteck/test/versions": _mock_response(200, [v1_data]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={},
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app,
            ["pull", "osteck/test", "--remote", "http://remote:8042", "--vault", str(tmp_path)],
        )
    assert result.exit_code == 0
    assert "Already up to date" in result.output


def test_pull_not_found_on_remote_exits_1(tmp_path: Path) -> None:
    client = _mock_http_client(
        get_map={"/osteck/missing": _mock_response(404)},
        post_map={},
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app,
            ["pull", "osteck/missing", "--remote", "http://r:8042", "--vault", str(tmp_path)],
        )
    assert result.exit_code == 1
    assert "not found on remote" in result.output


def test_pull_no_remote_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pull", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "CANTICA_REMOTE_URL" in result.output


def test_pull_with_certificate(tmp_path: Path) -> None:
    remote = VersionStore(tmp_path / "remote")
    r_prompt = remote.create_prompt("osteck", "test")
    r_v1 = remote.commit(r_prompt.id, "Hello", "First", "osteck")

    prompt_data = {
        "id": str(r_prompt.id),
        "namespace": "osteck",
        "name": "test",
        "description": "",
        "tags": [],
        "model_hints": [],
        "license": "MIT",
        "visibility": "public",
        "variables": [],
    }
    v1_data = {
        "sha": r_v1.sha,
        "content": "Hello",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": r_v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(r_prompt.id),
    }
    mock_client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, prompt_data),
            "/osteck/test/versions": _mock_response(200, [v1_data]),
            "/osteck/test/tags": _mock_response(200, []),
        },
        post_map={},
    )
    local_vault = tmp_path / "local"
    with patch("cantica.cli.httpx.Client") as mock_cls:
        mock_cls.return_value = mock_client
        result = runner.invoke(
            app,
            [
                "pull", "osteck/test",
                "--remote", "http://r:8042",
                "--certificate", "pull-cert-xyz",
                "--vault", str(local_vault),
            ],
        )
    assert result.exit_code == 0
    ctor_kwargs = mock_cls.call_args.kwargs
    assert ctor_kwargs["headers"].get("X-Cantica-Certificate") == "pull-cert-xyz"


def test_pull_imports_tags(tmp_path: Path) -> None:
    remote = VersionStore(tmp_path / "remote")
    r_prompt = remote.create_prompt("osteck", "test")
    r_v1 = remote.commit(r_prompt.id, "Hello world", "First", "osteck")

    v1_data = {
        "sha": r_v1.sha,
        "content": "Hello world",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": r_v1.created_at.isoformat(),
        "variables": [],
        "tags": ["v1.0"],
        "prompt_id": str(r_prompt.id),
    }
    prompt_data = {
        "namespace": "osteck",
        "name": "test",
        "description": "",
        "tags": [],
        "model_hints": [],
        "license": "MIT",
        "visibility": "public",
        "variables": [],
    }
    tag_data = {"name": "v1.0", "sha": r_v1.sha, "prompt_id": str(r_prompt.id)}
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, prompt_data),
            "/osteck/test/versions": _mock_response(200, [v1_data]),
            "/osteck/test/tags": _mock_response(200, [tag_data]),
        },
        post_map={},
    )
    local_vault = tmp_path / "local"
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app,
            ["pull", "osteck/test", "--remote", "http://r:8042", "--vault", str(local_vault)],
        )
    assert result.exit_code == 0
    local = VersionStore(local_vault)
    local_prompt = local.get_prompt("osteck", "test")
    assert local_prompt is not None
    assert local.get_tag(local_prompt.id, "v1.0") is not None


# --------------------------------------------------------------------------- #
# list                                                                         #
# --------------------------------------------------------------------------- #


def test_list_shows_prompts(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "osteck/test" in result.output


def test_list_no_prompts(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No prompts found" in result.output


def test_list_filter_by_tag(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_prompt("ns", "alpha", tags=["python"])
    store.create_prompt("ns", "beta", tags=["rust"])
    store.close()
    result = runner.invoke(app, ["list", "--tag", "python", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" not in result.output


def test_list_with_description(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_prompt("ns", "alpha", description="my description")
    store.close()
    result = runner.invoke(app, ["list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "my description" in result.output


# --------------------------------------------------------------------------- #
# search                                                                       #
# --------------------------------------------------------------------------- #


def test_search_finds_match(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_prompt("ns", "architect", description="design systems")
    store.close()
    result = runner.invoke(app, ["search", "architect", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "ns/architect" in result.output


def test_search_no_results(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(app, ["search", "xyzzy123", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No results found" in result.output


def test_search_with_tag_filter(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_prompt("ns", "alpha", description="architect", tags=["python"])
    store.create_prompt("ns", "beta", description="architect", tags=["rust"])
    store.close()
    result = runner.invoke(app, ["search", "architect", "--tag", "rust", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "beta" in result.output
    assert "alpha" not in result.output


# --------------------------------------------------------------------------- #
# star / unstar                                                                #
# --------------------------------------------------------------------------- #


def test_star_prompt(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    result = runner.invoke(app, ["star", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Starred osteck/test" in result.output


def test_star_missing_prompt(tmp_path: Path) -> None:
    result = runner.invoke(app, ["star", "nobody/ghost", "--vault", str(tmp_path)])
    assert result.exit_code == 1


def test_unstar_prompt(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.star_prompt("osteck", "test", "local")
    store.close()
    result = runner.invoke(app, ["unstar", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Unstarred osteck/test" in result.output


def test_unstar_not_starred(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    result = runner.invoke(app, ["unstar", "osteck/test", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "was not starred" in result.output


def test_unstar_missing_prompt(tmp_path: Path) -> None:
    result = runner.invoke(app, ["unstar", "nobody/ghost", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# comment                                                                      #
# --------------------------------------------------------------------------- #


def test_comment_adds_to_prompt(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    result = runner.invoke(app, ["comment", "osteck/test", "Nice prompt", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Comment" in result.output
    assert "added to osteck/test" in result.output


def test_comment_with_ref(tmp_path: Path) -> None:
    store, _, v1 = _seed(tmp_path)
    store.close()
    result = runner.invoke(
        app, ["comment", "osteck/test", "On v1", "--ref", v1.sha[:7], "--vault", str(tmp_path)]
    )
    assert result.exit_code == 0


def test_comment_with_bad_ref(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    result = runner.invoke(
        app, ["comment", "osteck/test", "text", "--ref", "nonexistent", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 1


def test_comment_missing_prompt(tmp_path: Path) -> None:
    result = runner.invoke(app, ["comment", "nobody/ghost", "hello", "--vault", str(tmp_path)])
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# collections                                                                  #
# --------------------------------------------------------------------------- #


def test_collections_lists_all(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_collection("ns", "favs", "My favs")
    store.create_collection("ns", "picks")
    store.close()
    result = runner.invoke(app, ["collections", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "ns/favs" in result.output
    assert "ns/picks" in result.output


def test_collections_no_collections(tmp_path: Path) -> None:
    result = runner.invoke(app, ["collections", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No collections found" in result.output


def test_collections_filter_by_namespace(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_collection("alice", "hers")
    store.create_collection("bob", "his")
    store.close()
    result = runner.invoke(app, ["collections", "--namespace", "alice", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "alice/hers" in result.output
    assert "bob/his" not in result.output


def test_collections_shows_description(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    store.create_collection("ns", "favs", "My favourites")
    store.close()
    result = runner.invoke(app, ["collections", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "My favourites" in result.output


# --------------------------------------------------------------------------- #
# lock / install                                                               #
# --------------------------------------------------------------------------- #


def test_lock_writes_lock_file(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    out = tmp_path / "out.lock"
    result = runner.invoke(
        app,
        ["lock", "osteck/test@latest", "--output", str(out), "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "Wrote 1 entry" in result.output


def test_lock_resolves_multiple_uris(tmp_path: Path) -> None:
    store = VersionStore(tmp_path)
    p1 = store.create_prompt("ns", "a")
    store.commit(p1.id, "c1", "m", "a")
    p2 = store.create_prompt("ns", "b")
    store.commit(p2.id, "c2", "m", "a")
    store.close()
    out = tmp_path / "out.lock"
    result = runner.invoke(
        app,
        ["lock", "ns/a@latest", "ns/b@latest", "--output", str(out), "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "Wrote 2 entries" in result.output


def test_lock_missing_prompt_exits_1(tmp_path: Path) -> None:
    out = tmp_path / "out.lock"
    result = runner.invoke(
        app,
        ["lock", "nobody/ghost@latest", "--output", str(out), "--vault", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert not out.exists()


def test_install_fetches_locked_versions(tmp_path: Path) -> None:
    # Standard library imports:
    import hashlib
    from datetime import UTC
    from datetime import datetime as _dt
    from unittest.mock import MagicMock
    from unittest.mock import patch as _patch

    # Local imports:
    from cantica.services.lock_file import LockEntry, LockFile, write_lock
    from cantica.services.version_store import _commit_sha

    content = "hello"
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    created_at = _dt(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    sha = _commit_sha(content_sha, None, "osteck", "First", created_at)

    now = _dt.now(UTC)
    lock = LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://remote.host/osteck/test@v1.0",
                namespace="osteck",
                name="test",
                ref="v1.0",
                sha=sha,
                locked_at=now,
            )
        ],
    )
    lock_out = tmp_path / "cantica.lock"
    write_lock(lock, lock_out)

    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {
        "sha": sha,
        "prompt_id": "pid",
        "branch": "main",
        "parent_sha": None,
        "message": "First",
        "author": "osteck",
        "content": content,
        "variables": [],
        "created_at": created_at.isoformat(),
        "tags": [],
    }

    with _patch("cantica.services.version_store.httpx.get", return_value=fake):
        result = runner.invoke(
            app, ["install", "--lock-file", str(lock_out), "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Fetched" in result.output
    store = VersionStore(tmp_path)
    v = store.get_version(sha)
    assert v is not None and v.content == "hello"
    store.close()


def test_install_skips_already_present(tmp_path: Path) -> None:
    store, _, _ = _seed(tmp_path)
    store.close()
    lock_out = tmp_path / "cantica.lock"
    runner.invoke(
        app, ["lock", "osteck/test@latest", "--output", str(lock_out), "--vault", str(tmp_path)]
    )
    # Install again — should skip
    result = runner.invoke(app, ["install", "--lock-file", str(lock_out), "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "already present" in result.output


def test_install_missing_lock_file_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["install", "--lock-file", str(tmp_path / "nonexistent.lock"), "--vault", str(tmp_path)],
    )
    assert result.exit_code == 1


def test_install_resolve_error_continues(tmp_path: Path) -> None:
    """When resolve_uri raises, the error is reported and install continues."""
    # Standard library imports:
    from datetime import UTC
    from datetime import datetime as _dt

    # Local imports:
    from cantica.services.lock_file import LockEntry, LockFile, write_lock

    now = _dt.now(UTC)
    lock = LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://host/ns/missing@v1",
                namespace="ns",
                name="missing",
                ref="v1",
                sha="a" * 64,
                locked_at=now,
            )
        ],
    )
    lock_out = tmp_path / "cantica.lock"
    write_lock(lock, lock_out)

    with patch("cantica.services.version_store.httpx.get", side_effect=KeyError("not found")):
        result = runner.invoke(
            app, ["install", "--lock-file", str(lock_out), "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Error fetching" in result.output


def test_install_sha_mismatch_warning(tmp_path: Path) -> None:
    """When resolved SHA differs from lock SHA, a warning is printed."""
    # Standard library imports:
    import hashlib
    from datetime import UTC
    from datetime import datetime as _dt

    # Local imports:
    from cantica.services.lock_file import LockEntry, LockFile, write_lock
    from cantica.services.version_store import _commit_sha

    content = "data"
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    created_at = _dt(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    real_sha = _commit_sha(content_sha, None, "osteck", "m", created_at)
    other_sha = "b" * 64  # lock contains a different SHA

    now = _dt.now(UTC)
    lock = LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://host/ns/p@v1",
                namespace="ns",
                name="p",
                ref="v1",
                sha=other_sha,
                locked_at=now,
            )
        ],
    )
    lock_out = tmp_path / "cantica.lock"
    write_lock(lock, lock_out)

    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {
        "sha": real_sha,
        "prompt_id": "pid",
        "branch": "main",
        "parent_sha": None,
        "message": "m",
        "author": "osteck",
        "content": content,
        "variables": [],
        "created_at": created_at.isoformat(),
        "tags": [],
    }

    with patch("cantica.services.version_store.httpx.get", return_value=fake):
        result = runner.invoke(
            app, ["install", "--lock-file", str(lock_out), "--vault", str(tmp_path)]
        )
    assert "Warning" in result.output


def test_install_creates_prompt_when_missing(tmp_path: Path) -> None:
    """When the prompt already exists locally, it is reused (False branch of prompt is None)."""
    # Standard library imports:
    import hashlib
    from datetime import UTC
    from datetime import datetime as _dt

    # Local imports:
    from cantica.services.lock_file import LockEntry, LockFile, write_lock
    from cantica.services.version_store import _commit_sha

    # Pre-create the prompt in the local vault
    store = VersionStore(tmp_path)
    prompt = store.create_prompt("ns", "ex")
    store.close()

    content = "hello"
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    created_at = _dt(2026, 5, 24, 9, 0, 0, tzinfo=UTC)
    sha = _commit_sha(content_sha, None, "a", "m", created_at)

    now = _dt.now(UTC)
    lock = LockFile(
        generated_at=now,
        prompts=[
            LockEntry(
                uri="cantica://host/ns/ex@v1",
                namespace="ns",
                name="ex",
                ref="v1",
                sha=sha,
                locked_at=now,
            )
        ],
    )
    lock_out = tmp_path / "cantica.lock"
    write_lock(lock, lock_out)

    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {
        "sha": sha,
        "prompt_id": prompt.id,
        "branch": "main",
        "parent_sha": None,
        "message": "m",
        "author": "a",
        "content": content,
        "variables": [],
        "created_at": created_at.isoformat(),
        "tags": [],
    }

    with patch("cantica.services.version_store.httpx.get", return_value=fake):
        result = runner.invoke(
            app, ["install", "--lock-file", str(lock_out), "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    assert "Fetched" in result.output


# --------------------------------------------------------------------------- #
# push — tag already on remote (skip)                                         #
# --------------------------------------------------------------------------- #


def test_push_skips_tag_already_on_remote(tmp_path: Path) -> None:
    """When the tag is already on the remote, it is skipped (no POST for that tag)."""
    store, prompt, v1 = _seed(tmp_path)
    store.create_tag(prompt.id, "v1.0", v1.sha)
    store.close()

    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, {"id": str(prompt.id)}),
            "/osteck/test/versions": _mock_response(200, [{"sha": v1.sha}]),
            "/osteck/test/tags": _mock_response(200, [{"name": "v1.0", "sha": v1.sha}]),
        },
        post_map={},
    )
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app, ["push", "osteck/test", "--remote", "http://r:8042", "--vault", str(tmp_path)]
        )
    assert result.exit_code == 0
    # v1.0 tag NOT pushed again — no tag POST calls
    assert "v1.0" not in result.output


# --------------------------------------------------------------------------- #
# pull — remote tag SHA not in local store                                    #
# --------------------------------------------------------------------------- #


def test_pull_skips_tag_for_unknown_sha(tmp_path: Path) -> None:
    """Tags whose SHA is not locally present are silently skipped."""
    remote = VersionStore(tmp_path / "remote")
    r_prompt = remote.create_prompt("osteck", "test")
    r_v1 = remote.commit(r_prompt.id, "Hello", "First", "osteck")
    remote.close()

    # Remote has a tag pointing to a totally different SHA we won't have locally.
    unknown_sha = "c" * 64
    prompt_data = {
        "namespace": "osteck",
        "name": "test",
        "description": "",
        "tags": [],
        "model_hints": [],
        "license": "MIT",
        "visibility": "public",
        "variables": [],
    }
    v1_data = {
        "sha": r_v1.sha,
        "content": "Hello",
        "message": "First",
        "author": "osteck",
        "branch": "main",
        "parent_sha": None,
        "created_at": r_v1.created_at.isoformat(),
        "variables": [],
        "tags": [],
        "prompt_id": str(r_prompt.id),
    }
    tag_data = {"name": "v1.0", "sha": unknown_sha}
    client = _mock_http_client(
        get_map={
            "/osteck/test": _mock_response(200, prompt_data),
            "/osteck/test/versions": _mock_response(200, [v1_data]),
            "/osteck/test/tags": _mock_response(200, [tag_data]),
        },
        post_map={},
    )
    local_vault = tmp_path / "local"
    with patch("cantica.cli.httpx.Client", return_value=client):
        result = runner.invoke(
            app,
            ["pull", "osteck/test", "--remote", "http://r:8042", "--vault", str(local_vault)],
        )
    assert result.exit_code == 0
    # The tag for the unknown SHA was skipped — tag name should not appear in output.
    assert "v1.0" not in result.output


# --------------------------------------------------------------------------- #
# namespace management CLI commands                                            #
# --------------------------------------------------------------------------- #


def test_namespace_new_creates_namespace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["namespace-new", "acme", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Created namespace acme" in result.output


def test_namespace_new_proprietary(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["namespace-new", "secret", "--proprietary", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "proprietary" in result.output


def test_namespace_new_encoded(tmp_path: Path) -> None:
    result = runner.invoke(app, ["namespace-new", "enc", "--encoded", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "encoded" in result.output


def test_namespace_new_all_flags(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["namespace-new", "both", "--proprietary", "--encoded", "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "proprietary" in result.output
    assert "encoded" in result.output


def test_namespace_list_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["namespace-list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No namespaces found" in result.output


def test_namespace_list_shows_namespaces(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "alice", "--vault", str(tmp_path)])
    runner.invoke(app, ["namespace-new", "bob", "--proprietary", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["namespace-list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "alice" in result.output
    assert "bob" in result.output
    assert "proprietary" in result.output


def test_namespace_list_shows_encoded_flag(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "encoded-ns", "--encoded", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["namespace-list", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "encoded" in result.output


def test_namespace_new_with_description(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["namespace-new", "acme", "-d", "ACME Corp", "--vault", str(tmp_path)],
    )
    assert result.exit_code == 0


# --------------------------------------------------------------------------- #
# certificate management CLI commands                                         #
# --------------------------------------------------------------------------- #


def test_cert_issue_success(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "priv", "--proprietary", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["cert-issue", "priv", "--to", "alice", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Certificate issued" in result.output
    assert "Token:" in result.output
    assert "Save the token" in result.output


def test_cert_issue_missing_namespace(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["cert-issue", "missing", "--to", "alice", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cert_issue_public_namespace_fails(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "pub", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["cert-issue", "pub", "--to", "alice", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cert_list_empty(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "priv", "--proprietary", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["cert-list", "priv", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "No certificates found" in result.output


def test_cert_list_shows_certs(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "priv", "--proprietary", "--vault", str(tmp_path)])
    runner.invoke(app, ["cert-issue", "priv", "--to", "alice", "--vault", str(tmp_path)])
    result = runner.invoke(app, ["cert-list", "priv", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "alice" in result.output


def test_cert_list_missing_namespace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["cert-list", "missing", "--vault", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cert_revoke_success(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "priv", "--proprietary", "--vault", str(tmp_path)])
    issue_result = runner.invoke(
        app, ["cert-issue", "priv", "--to", "alice", "--vault", str(tmp_path)]
    )
    # Extract cert ID from output
    for line in issue_result.output.splitlines():
        if line.strip().startswith("ID:"):
            cert_id = line.split("ID:")[1].strip()
            break
    result = runner.invoke(app, ["cert-revoke", cert_id, "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "Revoked" in result.output


def test_cert_revoke_not_found(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["cert-revoke", "00000000-0000-0000-0000-000000000000", "--vault", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cert_list_shows_revoked(tmp_path: Path) -> None:
    runner.invoke(app, ["namespace-new", "priv", "--proprietary", "--vault", str(tmp_path)])
    issue_result = runner.invoke(
        app, ["cert-issue", "priv", "--to", "alice", "--vault", str(tmp_path)]
    )
    for line in issue_result.output.splitlines():
        if line.strip().startswith("ID:"):
            cert_id = line.split("ID:")[1].strip()
            break
    runner.invoke(app, ["cert-revoke", cert_id, "--vault", str(tmp_path)])
    result = runner.invoke(app, ["cert-list", "priv", "--vault", str(tmp_path)])
    assert result.exit_code == 0
    assert "REVOKED" in result.output
