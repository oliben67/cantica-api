# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Local imports:
from cantica.models import Prompt, VariableSchema, Visibility


def test_prompt_slug() -> None:
    p = Prompt(namespace="osteck", name="architect")
    assert p.slug == "osteck/architect"


def test_prompt_defaults() -> None:
    p = Prompt(namespace="osteck", name="my-prompt")
    assert p.visibility == Visibility.public
    assert p.default_branch == "main"
    assert p.tags == []
    assert p.variables == []
    assert p.star_count == 0


def test_prompt_has_unique_id() -> None:
    p1 = Prompt(namespace="osteck", name="a")
    p2 = Prompt(namespace="osteck", name="b")
    assert p1.id != p2.id


def test_variable_schema_defaults() -> None:
    v = VariableSchema(name="language", default="Python")
    assert v.type == "string"
    assert not v.required
    assert v.description == ""


def test_variable_required_flag() -> None:
    v = VariableSchema(name="focus_area", required=True)
    assert v.required
    assert v.default is None


def test_visibility_enum_values() -> None:
    assert Visibility.public == "public"
    assert Visibility.private == "private"
    assert Visibility.unlisted == "unlisted"
    assert Visibility.team == "team"
