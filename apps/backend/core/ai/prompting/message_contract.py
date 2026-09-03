"""Compatibility metadata and ms-ai-fast-compatible Prompt message assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from apps.backend.core.ai.prompting.contracts import sha256_json

PROMPT_MESSAGE_CONTRACT_V1 = "prompt-message-contract.v1"


class PromptMessageContractError(ValueError):
    """Raised when frozen Prompt message metadata is malformed."""


def normalize_prompt_message_contract(
    value: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate legacy message metadata without changing the Gateway protocol."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PromptMessageContractError("prompt_message_contract_invalid")
    contract_version = value.get("contract_version")
    user_context_keys = value.get("user_context_keys")
    if (
        contract_version != PROMPT_MESSAGE_CONTRACT_V1
        or not isinstance(user_context_keys, list)
        or not user_context_keys
        or len(user_context_keys) != len(set(user_context_keys))
        or any(
            key not in {
                "SAFE_STUDY_CONTEXT_JSON",
                "PRIMARY_RESULT_JSON",
                "QUALITY_RESULTS_JSON",
                "ROUTE_CONTEXT_JSON",
                "STUDY_SCREENING_RESULT_JSON",
                "SYSTEM_ANALYSIS_RESULT_JSON",
                "FINAL_MEDICAL_RESULT_JSON",
                "REPORT_SCHEMA_JSON",
            }
            for key in user_context_keys
        )
        or (
            "SAFE_STUDY_CONTEXT_JSON" not in user_context_keys
            and set(user_context_keys)
            != {
                "FINAL_MEDICAL_RESULT_JSON",
                "QUALITY_RESULTS_JSON",
                "REPORT_SCHEMA_JSON",
            }
        )
    ):
        raise PromptMessageContractError("prompt_message_contract_invalid")
    return {
        "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
        "user_context_keys": list(user_context_keys),
    }


def validate_prompt_message_template(
    *,
    content: str,
    message_contract_json: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate frozen compatibility metadata; Nacos owns template semantics."""
    if not isinstance(content, str):
        raise PromptMessageContractError("prompt_content_invalid")
    return normalize_prompt_message_contract(message_contract_json)


@dataclass(frozen=True)
class RenderedPromptMessages:
    """Frozen ms-ai-fast-compatible messages without volatile signed image URLs."""

    messages_json: list[dict[str, Any]]
    messages_sha256: str
    contract_version: str | None


class PromptMessageAssembler:
    """Always send the fully rendered Nacos Prompt as one user message."""

    @classmethod
    def assemble(
        cls,
        *,
        rendered_text: str,
        message_contract_json: Mapping[str, Any] | None,
        safe_variables: Mapping[str, Any],
    ) -> RenderedPromptMessages:
        del safe_variables
        if not isinstance(rendered_text, str) or not rendered_text:
            raise PromptMessageContractError("rendered_prompt_messages_invalid")
        contract = normalize_prompt_message_contract(message_contract_json)
        messages = [{"role": "user", "content": rendered_text}]
        return RenderedPromptMessages(
            messages_json=messages,
            messages_sha256=sha256_json(messages),
            contract_version=(contract or {}).get("contract_version"),
        )


__all__ = [
    "PROMPT_MESSAGE_CONTRACT_V1",
    "PromptMessageAssembler",
    "PromptMessageContractError",
    "RenderedPromptMessages",
    "normalize_prompt_message_contract",
    "validate_prompt_message_template",
]
