# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
import re

# Local imports:
from cantica.models import VariableSchema

_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateEngine:
    """Variable substitution for prompt content using {{variable}} syntax."""

    def render(self, content: str, variables: dict[str, str]) -> str:
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise ValueError(f"missing variable: {key!r}")
            return variables[key]

        return _PATTERN.sub(_replace, content)

    def extract_variables(self, content: str) -> list[str]:
        """Return deduplicated variable names in order of first appearance."""
        return list(dict.fromkeys(_PATTERN.findall(content)))

    def validate(
        self,
        content: str,
        schema: list[VariableSchema],
        variables: dict[str, str],
    ) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        schema_map = {s.name: s for s in schema}

        for var in schema:
            if var.required and var.name not in variables:
                errors.append(f"required variable {var.name!r} is missing")

        for key in variables:
            if key not in schema_map:
                errors.append(f"unknown variable {key!r}")

        return errors

    def render_with_defaults(
        self,
        content: str,
        schema: list[VariableSchema],
        overrides: dict[str, str] | None = None,
    ) -> str:
        """Render using schema defaults, optionally overriding individual values."""
        variables: dict[str, str] = {}
        for var in schema:
            if var.default is not None:
                variables[var.name] = str(var.default)
        if overrides:
            variables.update(overrides)
        return self.render(content, variables)
