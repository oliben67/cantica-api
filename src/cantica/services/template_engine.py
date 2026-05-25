"""
Prompt template engine: ``{{variable}}`` substitution and schema validation.

``TemplateEngine`` renders prompt content by replacing ``{{name}}``
placeholders with caller-supplied values.  The double-brace syntax was chosen
to avoid conflicts with common prompt formats (e.g. Jinja2, Python f-strings).

Public API
----------
``render(content, variables)``
    Replace every ``{{key}}`` occurrence with ``variables[key]``.  Raises
    ``ValueError`` for any placeholder that has no matching key.

``extract_variables(content)``
    Return deduplicated variable names in order of first appearance.  Used
    when auto-detecting the variable schema from raw prompt text.

``validate(content, schema, variables)``
    Cross-check a set of runtime variables against a ``VariableSchema`` list.
    Returns a (possibly empty) list of error strings covering: required
    variables that are absent, and unknown variables not declared in the schema.

``render_with_defaults(content, schema, overrides)``
    Convenience wrapper that seeds the variable map from schema ``default``
    values before applying caller-supplied overrides, then calls ``render()``.
    Used by both the ``/render`` API endpoint and the ``cantica render`` CLI
    command.
"""

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
        """Substitute all ``{{variable}}`` placeholders in *content* using *variables*."""

        def _replace(match: re.Match[str]) -> str:
            """Replace a single ``{{var}}`` match with its value from *variables*."""
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
