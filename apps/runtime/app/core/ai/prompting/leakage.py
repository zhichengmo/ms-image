"""Recursive Prompt context leakage validation for target XRay calls."""

from __future__ import annotations

from typing import Any

from .contracts import PromptContractError


FORBIDDEN_CONTEXT_TOKENS = frozenset(
    {
        "gold",
        "truth",
        "annotation",
        "failure_bank",
        "score",
        "expected_status",
        "holdout",
        "signed_url",
        "api_key",
        "access_key",
        "base_url",
        "path",
        "filename",
        "previous_output",
    }
)
PRIMARY_ALLOWED_KEYS = frozenset(
    {
        "task_id",
        "study_revision_id",
        "ordered_image_refs",
        "species",
        "anatomy_regions",
        "view_positions",
        "coverage",
        "technical_limitations",
        "clinical_context_allowlist",
    }
)
TARGETED_EXTRA_ALLOWED_KEYS = frozenset(
    {
        "primary_complete_result",
        "selected_family_key",
        "selected_focus_key",
        "selected_strategy_key",
        "source_finding_ids",
        "coverage_proof",
        "route_reason_codes",
    }
)


def validate_primary_context(context: dict[str, Any]) -> None:
    _validate_context(context, PRIMARY_ALLOWED_KEYS)


def validate_targeted_context(context: dict[str, Any]) -> None:
    _validate_context(context, PRIMARY_ALLOWED_KEYS | TARGETED_EXTRA_ALLOWED_KEYS)


def _validate_context(context: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = set(context) - allowed
    if unknown:
        raise PromptContractError("prompt_context_fields_invalid")
    hits = _find_forbidden(context)
    if hits:
        raise PromptContractError("leakage_invalid")


def _find_forbidden(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).casefold()
            if key_text in FORBIDDEN_CONTEXT_TOKENS:
                hits.append(f"{path}.{key}")
            hits.extend(_find_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_find_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(token in lowered for token in FORBIDDEN_CONTEXT_TOKENS):
            hits.append(path)
    return hits


__all__ = [
    "PRIMARY_ALLOWED_KEYS",
    "TARGETED_EXTRA_ALLOWED_KEYS",
    "validate_primary_context",
    "validate_targeted_context",
]
