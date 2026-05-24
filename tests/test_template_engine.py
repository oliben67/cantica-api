# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest

# Local imports:
from cantica.models import VariableSchema
from cantica.services.template_engine import TemplateEngine


@pytest.fixture
def engine() -> TemplateEngine:
    return TemplateEngine()


def test_render_single(engine: TemplateEngine) -> None:
    assert engine.render("Hello {{name}}!", {"name": "world"}) == "Hello world!"


def test_render_multiple(engine: TemplateEngine) -> None:
    result = engine.render("{{greeting}}, {{name}}!", {"greeting": "Hi", "name": "Alice"})
    assert result == "Hi, Alice!"


def test_render_repeated_variable(engine: TemplateEngine) -> None:
    result = engine.render("{{x}} + {{x}}", {"x": "1"})
    assert result == "1 + 1"


def test_render_no_variables(engine: TemplateEngine) -> None:
    assert engine.render("No vars here", {}) == "No vars here"


def test_render_missing_variable_raises(engine: TemplateEngine) -> None:
    with pytest.raises(ValueError, match="missing variable"):
        engine.render("Hello {{name}}!", {})


def test_extract_variables_order(engine: TemplateEngine) -> None:
    vars_ = engine.extract_variables("{{role}} in {{language}}. Also {{language}}.")
    assert vars_ == ["role", "language"]


def test_extract_variables_empty(engine: TemplateEngine) -> None:
    assert engine.extract_variables("No vars") == []


def test_render_with_defaults(engine: TemplateEngine) -> None:
    schema = [
        VariableSchema(name="language", default="Python"),
        VariableSchema(name="role", default="architect"),
    ]
    result = engine.render_with_defaults("{{role}} using {{language}}", schema)
    assert result == "architect using Python"


def test_render_with_defaults_override(engine: TemplateEngine) -> None:
    schema = [VariableSchema(name="language", default="Python")]
    result = engine.render_with_defaults("{{language}}", schema, {"language": "Go"})
    assert result == "Go"


def test_validate_missing_required(engine: TemplateEngine) -> None:
    schema = [VariableSchema(name="focus", required=True)]
    errors = engine.validate("{{focus}}", schema, {})
    assert any("focus" in e for e in errors)


def test_validate_unknown_variable(engine: TemplateEngine) -> None:
    schema = [VariableSchema(name="language")]
    errors = engine.validate("{{language}}", schema, {"language": "Go", "extra": "val"})
    assert any("extra" in e for e in errors)


def test_validate_ok(engine: TemplateEngine) -> None:
    schema = [VariableSchema(name="language", required=True)]
    errors = engine.validate("{{language}}", schema, {"language": "Python"})
    assert errors == []


def test_validate_optional_missing_is_ok(engine: TemplateEngine) -> None:
    schema = [VariableSchema(name="language", required=False)]
    errors = engine.validate("{{language}}", schema, {})
    assert errors == []
