"""Shared Nacos Prompt source contracts for AI Control and Runtime workers.

The transport, coordinate mapping, payload parsing, and lifecycle live in this
neutral core module so both application boundaries reuse one qj-nacos client.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

try:
    from qj_nacos import NacosApiError, NacosClient, NacosConfig
except ImportError:  # pragma: no cover - production dependency validation
    NacosApiError = None
    NacosClient = None
    NacosConfig = None

from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.ai.prompting.renderer import PromptRenderError, PromptRenderer

PROMPT_SOURCE_RECEIPT_V1 = "prompt-source-receipt.v1"
NACOS_SOURCE_TYPE = "nacos"
NACOS_DEFAULT_VARIANT = "default"

# Keep the Prompt identity contract byte-for-byte compatible with ms-ai-fast.
NACOS_MODULE_CODE_MAP = {
    "intelligent_inquiry": "ai-doc",
    "image_recognition": "ai-pic",
    # XRay is an independent imaging modality in ms-image. Keep the
    # internal modality type stable as ``xray`` while exposing the readable
    # Nacos module segment ``x-ray``.
    "xray": "x-ray",
    "video_behavior_analysis": "video-behavior-analysis",
    "ai_voice": "ai-voice",
    "audio_recognition": "audio-recognition",
}

# XRay keeps the historical common Primary coordinate for frozen Task replay
# and uses exact species-specific coordinates for all new diagnostic releases.
NACOS_PROMPT_KEY_MAP = {
    ("xray", "xray_primary"): "primary",
    ("xray", "xray_cat_primary"): "primary",
    ("xray", "xray_dog_primary"): "primary",
    ("xray", "xray_cat_primary_adjudication"): "primary-adjudication",
    ("xray", "xray_dog_primary_adjudication"): "primary-adjudication",
    ("xray", "xray_cat_anatomy_localization"): "anatomy-localization",
    ("xray", "xray_dog_anatomy_localization"): "anatomy-localization",
    ("xray", "xray_cat_image_quality"): "image-quality",
    ("xray", "xray_dog_image_quality"): "image-quality",
    ("xray", "xray_cat_study_screening"): "study-screening",
    ("xray", "xray_dog_study_screening"): "study-screening",
    ("xray", "xray_cat_system_analysis"): "system-analysis",
    ("xray", "xray_dog_system_analysis"): "system-analysis",
    ("xray", "xray_cat_targeted_review"): "targeted-review",
    ("xray", "xray_dog_targeted_review"): "targeted-review",
    ("xray", "xray_cat_report_generation"): "report-generation",
    ("xray", "xray_dog_report_generation"): "report-generation",
}

# Every XRay coordinate is exact-only. ``common`` is historical compatibility,
# never a fallback for cat/dog, and the species coordinates cannot cross-fallback.
NACOS_XRAY_PROMPT_VARIANT_MAP = {
    "xray_primary": "common",
    "xray_cat_primary": "cat",
    "xray_dog_primary": "dog",
    "xray_cat_primary_adjudication": "cat",
    "xray_dog_primary_adjudication": "dog",
    "xray_cat_anatomy_localization": "cat",
    "xray_dog_anatomy_localization": "dog",
    "xray_cat_image_quality": "cat",
    "xray_dog_image_quality": "dog",
    "xray_cat_study_screening": "cat",
    "xray_dog_study_screening": "dog",
    "xray_cat_system_analysis": "cat",
    "xray_dog_system_analysis": "dog",
    "xray_cat_targeted_review": "cat",
    "xray_dog_targeted_review": "dog",
    "xray_cat_report_generation": "cat",
    "xray_dog_report_generation": "dog",
}
XRAY_PROMPT_VARIANTS = frozenset(NACOS_XRAY_PROMPT_VARIANT_MAP.values())


class PromptSourceError(ValueError):
    """Raised when an external Prompt Source cannot be read or parsed."""


class PromptSourceNotFoundError(PromptSourceError):
    """The exact Nacos Prompt key does not exist."""


class PromptSourceUnsafeError(PromptSourceError):
    """The imported template is invalid for the shared rendering contract."""


@dataclass(frozen=True)
class ImportedPromptRecord:
    template: str
    version: str = ""
    label: str = ""
    md5: str = ""
    output_schema: dict[str, Any] | None = None


def nacos_data_id(
    *,
    service_code: str,
    module_code: str,
    prompt_key: str,
    variant: str,
    locale: str,
) -> str:
    """Build ``service.module.prompt.variant.locale`` like ms-ai-fast."""
    values = {
        "service_code": service_code,
        "module_code": module_code,
        "prompt_key": prompt_key,
        "variant": variant,
        "locale": locale,
    }
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise PromptSourceError(f"prompt_source_{name}_invalid")
    normalized_module_code = module_code.strip()
    normalized_prompt_key = prompt_key.strip()
    normalized_variant = variant.strip()
    if normalized_module_code == "xray":
        expected_variant = NACOS_XRAY_PROMPT_VARIANT_MAP.get(
            normalized_prompt_key
        )
        if expected_variant is None:
            raise PromptSourceError("prompt_source_xray_prompt_key_invalid")
        if normalized_variant != expected_variant:
            raise PromptSourceError("prompt_source_xray_variant_mismatch")
    target_module = NACOS_MODULE_CODE_MAP.get(
        normalized_module_code, normalized_module_code
    )
    target_prompt_key = NACOS_PROMPT_KEY_MAP.get(
        (normalized_module_code, normalized_prompt_key),
        normalized_prompt_key.replace("_", "-"),
    )
    return (
        f"{service_code.strip()}.{target_module}.{target_prompt_key}."
        f"{normalized_variant}.{locale.strip()}"
    )


def variant_candidates(
    requested_variant: str,
    *,
    module_code: str | None = None,
) -> list[str]:
    """Resolve Nacos variants, fail-closing XRay before generic fallback.

    Existing modules retain the ms-ai-fast lookup order ``requested`` then
    ``default``. XRay uses exact ``common``/``cat``/``dog`` Primary coordinates
    and never falls back between them or to ``default``.
    """
    if not isinstance(requested_variant, str):
        raise PromptSourceError("prompt_source_variant_invalid")
    if module_code is not None and not isinstance(module_code, str):
        raise PromptSourceError("prompt_source_module_code_invalid")
    requested = requested_variant.strip() or NACOS_DEFAULT_VARIANT
    normalized_module_code = module_code.strip() if module_code is not None else ""
    if normalized_module_code == "xray":
        if requested not in XRAY_PROMPT_VARIANTS:
            raise PromptSourceError("prompt_source_xray_variant_invalid")
        return [requested]
    candidates = [requested]
    if requested != NACOS_DEFAULT_VARIANT:
        candidates.append(NACOS_DEFAULT_VARIANT)
    return candidates


def normalize_imported_prompt(content: str) -> tuple[str, dict[str, Any]]:
    """Keep the Nacos body unchanged and freeze its Jinja/$variable contract.

    Rendering intentionally follows ms-ai-fast: Jinja2 ``StrictUndefined``, the
    ``tojson`` filter and ``$variable`` replacement. This function does not
    translate business variable names into a second ``SAFE_*`` template language.
    """
    if not isinstance(content, str) or not content:
        raise PromptSourceError("prompt_source_content_empty")
    normalized = content.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    try:
        referenced = PromptRenderer.template_variables(normalized)
    except PromptRenderError as exc:
        raise PromptSourceUnsafeError("prompt_source_template_invalid") from exc
    variables = {
        "contract_version": "prompt-variables.v1",
        "required": sorted(referenced),
        "optional": [],
    }
    return normalized, variables


def build_source_receipt(
    *,
    source_type: str,
    namespace: str,
    source_key: str,
    release_or_version: str,
    requested_variant: str,
    resolved_variant: str,
    fallback_used: bool,
    content_sha256: str,
    imported_at: str | None = None,
) -> dict[str, Any]:
    """Build the frozen source receipt without credentials or Prompt body."""
    if source_type != NACOS_SOURCE_TYPE:
        raise PromptSourceError("prompt_source_type_unsupported")
    for name, value in {
        "namespace": namespace,
        "source_key": source_key,
        "release_or_version": release_or_version,
        "requested_variant": requested_variant,
        "resolved_variant": resolved_variant,
        "content_sha256": content_sha256,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise PromptSourceError(f"prompt_source_receipt_{name}_invalid")
    if len(content_sha256) != 64:
        raise PromptSourceError("prompt_source_receipt_content_sha_invalid")
    return {
        "contract_version": PROMPT_SOURCE_RECEIPT_V1,
        "source_type": source_type,
        "namespace": namespace.strip(),
        "source_key": source_key.strip(),
        "release_or_version": release_or_version.strip(),
        "requested_variant": requested_variant.strip(),
        "resolved_variant": resolved_variant.strip(),
        "fallback_used": bool(fallback_used),
        "content_sha256": content_sha256,
        "imported_at": imported_at
        or datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    return sha256_json(dict(receipt))


def parse_nacos_prompt_payload(payload: Any) -> ImportedPromptRecord:
    """Parse the same Nacos Prompt envelopes accepted by ms-ai-fast."""
    if payload is None:
        raise PromptSourceError("prompt_source_nacos_payload_empty")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PromptSourceError("prompt_source_nacos_payload_invalid") from exc
    if isinstance(payload, Mapping) and isinstance(payload.get("data"), Mapping):
        payload = payload["data"]
    if not isinstance(payload, Mapping):
        raise PromptSourceError("prompt_source_nacos_payload_invalid")

    template_value = next(
        (
            payload.get(field_name)
            for field_name in (
                "promptTemplate",
                "prompt_template",
                "template",
                "content",
                "value",
                "prompt",
            )
            if payload.get(field_name) is not None
        ),
        None,
    )
    if isinstance(template_value, Mapping):
        template_value = json.dumps(template_value, ensure_ascii=False)
    if not isinstance(template_value, str) or not template_value.strip():
        raise PromptSourceError("prompt_source_nacos_template_missing")

    output_value = payload.get("output")
    envelope = _decode_json_mapping(template_value)
    if envelope is not None and isinstance(envelope.get("prompt"), str):
        template_value = envelope["prompt"]
        output_value = output_value or envelope.get("output")
    if not template_value.strip():
        raise PromptSourceError("prompt_source_nacos_template_missing")

    output_schema = _output_schema_from_value(output_value)
    if output_schema is None:
        for container in (payload, envelope or {}):
            for field_name in ("outputSchema", "output_schema", "schema"):
                candidate = _decode_json_mapping(container.get(field_name))
                if candidate:
                    output_schema = candidate
                    break
            if output_schema is not None:
                break

    return ImportedPromptRecord(
        template=template_value,
        version=str(payload.get("version") or ""),
        label=str(payload.get("label") or payload.get("release") or ""),
        md5=str(payload.get("md5") or ""),
        output_schema=output_schema,
    )


def _decode_json_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return dict(decoded) if isinstance(decoded, Mapping) else None


def _output_schema_from_value(value: Any) -> dict[str, Any] | None:
    output = _decode_json_mapping(value)
    if not output:
        return None
    output_type = str(output.get("type") or output.get("format") or "").lower()
    if output_type in {"json", "json_schema"}:
        return _decode_json_mapping(output.get("schema"))
    if output_type in {"object", "array"} or any(
        key in output for key in ("properties", "$defs", "required", "items")
    ):
        return output
    return None


class NacosPromptSourceClient:
    """Small qj-nacos client matching ms-ai-fast's Prompt lookup contract."""

    def __init__(
        self,
        *,
        server_addr: str,
        namespace_id: str,
        context_path: str = "/nacos",
        username: str = "",
        password: str = "",
        timeout_seconds: float = 10.0,
        caller_service: str = "ms-image",
        client: Any | None = None,
    ):
        if not server_addr or not namespace_id:
            raise PromptSourceError("prompt_source_nacos_not_configured")
        self.namespace_id = namespace_id.strip()
        self._server_addr = server_addr.strip()
        self._context_path = context_path.strip() or "/nacos"
        self._username = username.strip()
        self._password = password
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._caller_service = caller_service.strip() or "ms-image"
        self._client = client
        self._owns_client = client is None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is not None:
                return self._client
            if NacosClient is None or NacosConfig is None:
                raise PromptSourceError("prompt_source_nacos_dependency_missing")
            try:
                config = NacosConfig(
                    enabled=True,
                    server_addr=self._server_addr,
                    context_path=self._context_path,
                    username=self._username,
                    password=self._password,
                    namespace_id=self.namespace_id,
                    config_enabled=False,
                    discovery_enabled=False,
                    http_timeout_seconds=self._timeout_seconds,
                )
                self._client = await NacosClient(
                    self._caller_service,
                    config,
                ).start()
            except Exception as exc:
                raise PromptSourceError("prompt_source_nacos_unavailable") from exc
            return self._client

    async def fetch(
        self,
        *,
        data_id: str,
        version: str | None = None,
        label: str | None = None,
    ) -> Mapping[str, Any] | None:
        params: dict[str, str | None] = {
            "namespaceId": self.namespace_id,
            "promptKey": data_id,
            "version": version or None,
            "label": label or None,
        }
        client = await self._get_client()
        try:
            payload = await client.request(
                "GET",
                "/v3/client/ai/prompt",
                params=params,
            )
        except Exception as exc:
            if self._is_nacos_not_found(exc):
                return None
            code = getattr(exc, "code", None)
            if isinstance(code, int):
                raise PromptSourceError(f"prompt_source_nacos_http_{code}") from exc
            raise PromptSourceError("prompt_source_nacos_unavailable") from exc
        if not isinstance(payload, Mapping):
            raise PromptSourceError("prompt_source_nacos_payload_invalid")
        return payload

    async def check_prompt_api_readiness(self) -> None:
        """Verify the Prompt Client route without reading business Prompt data.

        Nacos deployments do not expose one stable Console health route across
        versions and gateways.  AI Control depends on the Prompt Client API, so
        probe that exact route with ``OPTIONS`` and require GET support.  Client
        startup still performs the configured login first, which also validates
        reachability and credentials without coupling readiness to one mutable
        Prompt key.
        """

        client = await self._get_client()
        try:
            response = await client.request(
                "OPTIONS",
                "/v3/client/ai/prompt",
                params={"namespaceId": self.namespace_id},
                response_mode="response",
            )
        except Exception as exc:
            raise PromptSourceError("prompt_source_nacos_unavailable") from exc

        status_code = getattr(response, "status_code", None)
        headers = getattr(response, "headers", None)
        if (
            not isinstance(status_code, int)
            or status_code < 200
            or status_code >= 300
            or not isinstance(headers, Mapping)
        ):
            raise PromptSourceError("prompt_source_nacos_readiness_invalid")
        allowed_methods = {
            item.strip().upper()
            for item in str(headers.get("allow") or "").split(",")
            if item.strip()
        }
        if "GET" not in allowed_methods:
            raise PromptSourceError("prompt_source_nacos_prompt_api_unavailable")

    @staticmethod
    def _is_nacos_not_found(exc: Exception) -> bool:
        if NacosApiError is not None and not isinstance(exc, NacosApiError):
            return False
        if getattr(exc, "code", None) == 404:
            return True
        message = str(exc).lower()
        return "404" in message or "resource not found" in message

    async def aclose(self) -> None:
        client = self._client
        self._client = None
        if client is None or not self._owns_client:
            return
        for method_name in ("close", "stop", "shutdown"):
            method = getattr(client, method_name, None)
            if method is None:
                continue
            result = method()
            if hasattr(result, "__await__"):
                await result
            return


__all__ = [
    "ImportedPromptRecord",
    "NACOS_DEFAULT_VARIANT",
    "NACOS_MODULE_CODE_MAP",
    "NACOS_PROMPT_KEY_MAP",
    "NACOS_SOURCE_TYPE",
    "NACOS_XRAY_PROMPT_VARIANT_MAP",
    "NacosPromptSourceClient",
    "PROMPT_SOURCE_RECEIPT_V1",
    "PromptSourceError",
    "PromptSourceNotFoundError",
    "PromptSourceUnsafeError",
    "build_source_receipt",
    "nacos_data_id",
    "normalize_imported_prompt",
    "parse_nacos_prompt_payload",
    "receipt_sha256",
    "variant_candidates",
    "XRAY_PROMPT_VARIANTS",
]
