"""Frozen contracts around the ms-ai-fast-compatible AI Platform request path.

The Gateway boundary receives immutable task facts and returns parsed audit facts.
It never reads mutable Prompt/Nacos state, resolves a separate Secret reference, or
persists Provider response bodies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from apps.backend.core.ai.prompting.contracts import canonical_json, sha256_json

GATEWAY_PROFILE_V1 = "ai-gateway-profile.v1"
AI_IMAGE_RECEIPT_V1 = "ai-image-receipt.v1"
AI_IMAGE_RECEIPT_V2 = "ai-image-receipt.v2"
_JSON_MARKDOWN_FENCE = re.compile(
    r"\A```json[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*\Z"
)


class GatewayContractError(ValueError):
    """Raised when frozen Gateway input or Provider output violates a contract."""


class GatewayDefiniteResponseError(GatewayContractError):
    """A definite Provider response failed its technical output contract."""

    def __init__(
        self,
        error_code: str,
        *,
        image_receipt: Mapping[str, Any],
        image_manifest_sha256: str | None,
        image_count_sent: int,
        provider_request_id: str | None = None,
        actual_model: str | None = None,
        usage_json: Mapping[str, Any] | None = None,
        response_sha256: str | None = None,
    ) -> None:
        super().__init__(error_code)
        self.image_receipt = dict(image_receipt)
        self.image_manifest_sha256 = image_manifest_sha256
        self.image_count_sent = image_count_sent
        self.provider_request_id = provider_request_id
        self.actual_model = actual_model
        self.usage_json = (
            dict(usage_json) if isinstance(usage_json, Mapping) else None
        )
        self.response_sha256 = response_sha256


class GatewayRejectedError(GatewayDefiniteResponseError):
    """A Provider definitely returned a terminal HTTP rejection."""


class GatewayUnknownDeliveryError(GatewayContractError):
    """The Provider may have accepted a request but the outcome is uncertain."""


def normalize_gateway_profile(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate the frozen profile controlling one AI Platform attempt."""
    if value is None:
        return {
            "contract_version": GATEWAY_PROFILE_V1,
            "adapter_key": "openai-compatible",
            "provider_enabled": False,
            "qualification_status": "disabled",
            "streaming_mode": "json",
            "image_url_ttl_seconds": 300,
            "allowed_actual_models": [],
        }
    if not isinstance(value, Mapping):
        raise GatewayContractError("gateway_profile_invalid")
    contract_version = value.get("contract_version")
    adapter_key = value.get("adapter_key")
    provider_enabled = value.get("provider_enabled")
    qualification_status = value.get("qualification_status")
    streaming_mode = value.get("streaming_mode", "json")
    image_url_ttl_seconds = value.get("image_url_ttl_seconds", 300)
    allowed_actual_models = value.get("allowed_actual_models", [])
    if (
        contract_version != GATEWAY_PROFILE_V1
        or adapter_key != "openai-compatible"
        or not isinstance(provider_enabled, bool)
        or qualification_status not in {"disabled", "qualified"}
        or streaming_mode not in {"json", "aggregate_sse"}
        or not isinstance(image_url_ttl_seconds, int)
        or isinstance(image_url_ttl_seconds, bool)
        or not 30 <= image_url_ttl_seconds <= 900
        or not isinstance(allowed_actual_models, list)
        or not all(
            isinstance(item, str) and item.strip() and len(item.strip()) <= 128
            for item in allowed_actual_models
        )
    ):
        raise GatewayContractError("gateway_profile_invalid")
    normalized_models = sorted({item.strip() for item in allowed_actual_models})
    if provider_enabled and qualification_status != "qualified":
        raise GatewayContractError("gateway_profile_qualification_required")
    if provider_enabled and not normalized_models:
        raise GatewayContractError("gateway_profile_actual_models_required")
    if not provider_enabled and qualification_status != "disabled":
        raise GatewayContractError("gateway_profile_disabled_state_invalid")
    return {
        "contract_version": GATEWAY_PROFILE_V1,
        "adapter_key": "openai-compatible",
        "provider_enabled": provider_enabled,
        "qualification_status": qualification_status,
        "streaming_mode": streaming_mode,
        "image_url_ttl_seconds": image_url_ttl_seconds,
        "allowed_actual_models": normalized_models,
    }


def validate_signed_image_url(value: str, *, allowed_hosts: Iterable[str]) -> str:
    """Accept only an HTTPS URL from the configured OSS bucket/endpoint hosts."""
    if not isinstance(value, str) or not value:
        raise GatewayContractError("ai_image_signed_url_invalid")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise GatewayContractError("ai_image_signed_url_invalid") from exc
    normalized_allowed_hosts = {
        host.casefold().strip() for host in allowed_hosts if host
    }
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path
        or parsed.hostname.casefold() not in normalized_allowed_hosts
    ):
        raise GatewayContractError("ai_image_signed_url_invalid")
    return value


def schema_validate_result(*, value: Any, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Parse Provider message content and validate the frozen strict schema."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("```"):
            fenced = _JSON_MARKDOWN_FENCE.fullmatch(stripped)
            if fenced is None or "```" in fenced.group("body"):
                raise GatewayContractError("provider_response_json_invalid")
            value = fenced.group("body").strip()
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GatewayContractError("provider_response_json_invalid") from exc
    if not isinstance(value, dict) or not isinstance(schema, Mapping):
        raise GatewayContractError("provider_response_schema_invalid")
    try:
        Draft202012Validator.check_schema(dict(schema))
        Draft202012Validator(dict(schema)).validate(value)
    except SchemaError as exc:
        raise GatewayContractError("frozen_output_schema_invalid") from exc
    except ValidationError as exc:
        raise GatewayContractError("provider_response_schema_rejected") from exc
    return value


@dataclass(frozen=True)
class GatewayImageInput:
    """Ephemeral signed image URL: never persist this object or its URL."""

    sequence_no: int
    mime_type: str
    signed_url: str = field(repr=False)


@dataclass(frozen=True)
class GatewayRequest:
    """Non-secret facts frozen for one physical AI Platform Attempt."""

    attempt_id: str
    logical_call_id: str
    task_id: str
    trace_id: str
    request_id: str
    connection_sha256: str
    provider_type: str
    api_format: str
    requested_model: str
    allowed_actual_models: tuple[str, ...]
    generation_params: Mapping[str, Any]
    response_schema: Mapping[str, Any]
    messages: tuple[Mapping[str, Any], ...]
    images: tuple[GatewayImageInput, ...]
    timeout_ms: int
    provider_idempotency_key: str
    image_manifest_sha256: str | None

    def request_sha256(self) -> str:
        """Hash canonical request intent without API Key or short-lived URLs."""
        return sha256_json(
            {
                "contract_version": "ai-gateway-request.v1",
                "attempt_id": self.attempt_id,
                "logical_call_id": self.logical_call_id,
                "task_id": self.task_id,
                "connection_sha256": self.connection_sha256,
                "provider_type": self.provider_type,
                "api_format": self.api_format,
                "requested_model": self.requested_model,
                "allowed_actual_models": list(self.allowed_actual_models),
                "generation_params": dict(self.generation_params),
                "response_schema": dict(self.response_schema),
                "messages": list(self.messages),
                "image_manifest_sha256": self.image_manifest_sha256,
                "image_count": len(self.images),
                "timeout_ms": self.timeout_ms,
            }
        )


@dataclass(frozen=True)
class GatewayExecutionResult:
    """Schema-accepted result and non-sensitive Provider audit facts."""

    provider_request_id: str
    actual_model: str
    usage_json: dict[str, Any] | None
    parsed_result_json: dict[str, Any]
    response_sha256: str
    duration_ms: int
    transport_mode: str = "json"


def response_sha256(provider_response: Mapping[str, Any]) -> str:
    """Hash the canonical Provider JSON body without persisting that body."""
    if not isinstance(provider_response, Mapping):
        raise GatewayContractError("provider_response_payload_invalid")
    return sha256_json(dict(provider_response))


def canonical_user_context(value: Mapping[str, Any]) -> str:
    """Produce deterministic JSON text for compatibility callers."""
    return canonical_json(dict(value))


__all__ = [
    "AI_IMAGE_RECEIPT_V1",
    "AI_IMAGE_RECEIPT_V2",
    "GATEWAY_PROFILE_V1",
    "GatewayContractError",
    "GatewayDefiniteResponseError",
    "GatewayExecutionResult",
    "GatewayImageInput",
    "GatewayRejectedError",
    "GatewayRequest",
    "GatewayUnknownDeliveryError",
    "canonical_user_context",
    "normalize_gateway_profile",
    "response_sha256",
    "schema_validate_result",
    "validate_signed_image_url",
]
