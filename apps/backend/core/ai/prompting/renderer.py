"""Frozen Prompt rendering with the same template semantics as ms-ai-fast."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError, meta

from .contracts import sha256_json, sha256_text

_VARIABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_DOLLAR_PATTERN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


class PromptRenderError(ValueError):
    """Raised when a frozen Prompt cannot be rendered deterministically."""


@dataclass(frozen=True)
class RenderedPrompt:
    rendered_text: str
    rendered_prompt_sha256: str
    context_sha256: str


def normalize_prompt_content(value: str) -> str:
    if not isinstance(value, str):
        raise PromptRenderError("prompt_content_invalid")
    return value.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _jinja_environment() -> Environment:
    environment = Environment(
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    environment.filters["tojson"] = _to_json
    return environment


class PromptRenderer:
    """Render frozen Prompt text exactly like ms-ai-fast's Nacos runtime path."""

    @classmethod
    def declared_variables(
        cls, variables_json: Mapping[str, Any]
    ) -> tuple[set[str], set[str]]:
        if not isinstance(variables_json, Mapping):
            raise PromptRenderError("prompt_variables_contract_invalid")
        if variables_json.get("contract_version") != "prompt-variables.v1":
            raise PromptRenderError("prompt_variables_contract_version_invalid")
        required = variables_json.get("required")
        optional = variables_json.get("optional")
        if not isinstance(required, list) or not isinstance(optional, list):
            raise PromptRenderError("prompt_variables_contract_invalid")
        names = [*required, *optional]
        if (
            not all(isinstance(name, str) and _VARIABLE_NAME.fullmatch(name) for name in names)
            or len(names) != len(set(names))
        ):
            raise PromptRenderError("prompt_variables_contract_invalid")
        return set(required), set(optional)

    @classmethod
    def template_variables(cls, content: str) -> set[str]:
        normalized = normalize_prompt_content(content)
        environment = _jinja_environment()
        try:
            parsed = environment.parse(normalized)
        except TemplateError as exc:
            raise PromptRenderError("prompt_template_invalid") from exc
        return set(meta.find_undeclared_variables(parsed)) | set(
            _DOLLAR_PATTERN.findall(normalized)
        )

    @classmethod
    def validate_template(
        cls, *, content: str, variables_json: Mapping[str, Any]
    ) -> str:
        normalized = normalize_prompt_content(content)
        required, optional = cls.declared_variables(variables_json)
        referenced = cls.template_variables(normalized)
        if not referenced.issubset(required | optional):
            raise PromptRenderError("prompt_placeholder_undeclared")
        try:
            _jinja_environment().from_string(normalized)
        except TemplateError as exc:
            raise PromptRenderError("prompt_template_invalid") from exc
        return normalized

    @classmethod
    def render(
        cls,
        *,
        content: str,
        variables_json: Mapping[str, Any],
        safe_variables: Mapping[str, Any],
        max_prompt_chars: int,
    ) -> RenderedPrompt:
        normalized = cls.validate_template(
            content=content,
            variables_json=variables_json,
        )
        required, optional = cls.declared_variables(variables_json)
        missing = sorted(required - set(safe_variables))
        unexpected = sorted(set(safe_variables) - required - optional)
        if missing:
            raise PromptRenderError("prompt_required_variable_missing")
        if unexpected:
            raise PromptRenderError("prompt_variable_not_declared")
        variables = {
            name: safe_variables[name]
            for name in required | optional
            if name in safe_variables
        }
        try:
            rendered = _jinja_environment().from_string(normalized).render(**variables)
        except TemplateError as exc:
            raise PromptRenderError("prompt_template_render_failed") from exc

        missing_dollar = sorted(
            {name for name in _DOLLAR_PATTERN.findall(rendered) if name not in variables}
        )
        if missing_dollar:
            raise PromptRenderError("prompt_required_variable_missing")

        def replace_placeholder(match: re.Match[str]) -> str:
            value = variables[match.group(1)]
            if isinstance(value, (dict, list, tuple, bool, int, float)):
                return _to_json(value)
            return "" if value is None else str(value)

        rendered = _DOLLAR_PATTERN.sub(replace_placeholder, rendered)
        if not rendered or len(rendered) > max_prompt_chars:
            raise PromptRenderError("prompt_rendered_length_invalid")
        context = {name: variables[name] for name in sorted(variables)}
        return RenderedPrompt(
            rendered_text=rendered,
            rendered_prompt_sha256=sha256_text(rendered),
            context_sha256=sha256_json(context),
        )


__all__ = [
    "PromptRenderError",
    "PromptRenderer",
    "RenderedPrompt",
    "normalize_prompt_content",
]
