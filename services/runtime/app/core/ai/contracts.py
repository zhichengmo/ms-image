"""Provider-neutral contracts for the first real AI qualification slice.

The contracts deliberately carry image bytes only in worker memory.  Broker
messages, logs and persisted receipts must use opaque identifiers and hashes.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol


ALLOWED_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
)
ALLOWED_PROVIDER_ERROR_CLASSES = frozenset(
    {
        "provider_auth",
        "endpoint_timeout",
        "network_unreachable",
        "tls_failure",
        "model_invalid",
        "schema_invalid",
        "rate_limited",
        "provider_unavailable",
        "provider_receipt_missing",
        "provider_receipt_unsupported",
        "provider_egress_proof_invalid",
        "egress_proof_signing_key_missing",
        "provider_output_contract",
        "provider_configuration_incomplete",
        "provider_disabled",
        "provider_not_qualified",
        "image_manifest_not_resolved",
        "model_mismatch",
    }
)
ALLOWED_FULL_SENT_STATES = frozenset(
    {"unknown", "confirmed", "partial", "over_budget", "not_applicable"}
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def ordered_image_identity_sha256(
    identities: Iterable[tuple[int, str]],
) -> str:
    """Hash an ordered sequence of source indices and raw-byte hashes."""

    payload = "\n".join(
        f"{source_index}:{sent_sha256}"
        for source_index, sent_sha256 in identities
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ordered_image_sha256(images: tuple["ProviderImageInput", ...]) -> str:
    """Hash the ordered source index and raw bytes hash, never image bytes."""

    return ordered_image_identity_sha256(
        (image.source_index, image.sent_sha256 or "") for image in images
    )


@dataclass(frozen=True)
class AIConnectionConfig:
    connection_id: str
    family: str
    base_url: str
    model: str
    api_key_ref: str
    enabled: bool = True
    cooldown_seconds: float = 30.0

    def __post_init__(self) -> None:
        if (
            not self.connection_id.strip()
            or not self.family.strip()
            or not self.model.strip()
            or not self.api_key_ref.strip()
            or self.cooldown_seconds < 0
        ):
            raise ValueError("ai_connection_config_invalid")


@dataclass(frozen=True)
class AIRequestPolicy:
    max_attempts: int = 3
    hard_timeout_seconds: float = 30.0
    grace_timeout_seconds: float = 2.0
    backoff_base_seconds: float = 0.0
    max_backoff_seconds: float = 30.0
    concurrency: int = 20

    def __post_init__(self) -> None:
        if (
            self.max_attempts <= 0
            or self.hard_timeout_seconds <= 0
            or self.grace_timeout_seconds < 0
            or self.max_backoff_seconds < 0
            or self.backoff_base_seconds < 0
            or self.concurrency <= 0
        ):
            raise ValueError("ai_request_policy_invalid")


@dataclass(frozen=True)
class ProviderImageInput:
    source_index: int
    source_image_ref: str
    mime_type: str
    content: bytes = field(repr=False, compare=False)
    pixel_width: int
    pixel_height: int
    sent_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.source_index < 0:
            raise ValueError("image_source_index_invalid")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}", self.source_image_ref):
            raise ValueError("image_ref_must_be_opaque")
        if self.mime_type.casefold() not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("image_mime_type_not_allowed")
        if not self.content:
            raise ValueError("image_content_empty")
        if self.pixel_width <= 0 or self.pixel_height <= 0:
            raise ValueError("image_dimensions_invalid")
        digest = sha256_bytes(self.content)
        if self.sent_sha256 is not None and self.sent_sha256 != digest:
            raise ValueError("image_sent_hash_mismatch")
        object.__setattr__(self, "sent_sha256", digest)

    @property
    def byte_size(self) -> int:
        return len(self.content)

    def receipt_identity(self) -> dict[str, Any]:
        """Return safe per-image metadata without refs, URLs or bytes."""
        return {
            "source_index": self.source_index,
            "sent_sha256": self.sent_sha256,
            "mime_type": self.mime_type,
            "byte_size": self.byte_size,
            "pixel_width": self.pixel_width,
            "pixel_height": self.pixel_height,
        }


@dataclass(frozen=True)
class ProviderRequest:
    run_id: str
    attempt_id: str
    node_key: str
    release_fingerprint: str
    prompt: Any
    response_schema_key: str
    requested_model: str
    images: tuple[ProviderImageInput, ...] = ()
    response_schema: dict[str, Any] | None = None
    full_sent: str | None = None
    request_nonce: str | None = None
    deadline_seconds: float | None = None
    connection_id: str | None = None
    response_schema_sha256: str | None = None

    def __post_init__(self) -> None:
        required_strings = (
            self.run_id,
            self.attempt_id,
            self.node_key,
            self.release_fingerprint,
            self.response_schema_key,
            self.requested_model,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_strings):
            raise ValueError("provider_request_identity_invalid")
        rendered_body = getattr(self.prompt, "rendered_body", "")
        if not isinstance(rendered_body, str) or not rendered_body.strip():
            raise ValueError("provider_prompt_invalid")
        if self.response_schema is not None and not isinstance(self.response_schema, dict):
            raise ValueError("provider_response_schema_invalid")
        indices = [image.source_index for image in self.images]
        if indices != list(range(len(indices))):
            raise ValueError("provider_image_order_invalid")
        if self.deadline_seconds is not None and self.deadline_seconds <= 0:
            raise ValueError("provider_deadline_invalid")
        if self.request_nonce is not None and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{15,127}", self.request_nonce
        ):
            raise ValueError("provider_request_nonce_invalid")
        if self.full_sent is None:
            object.__setattr__(
                self,
                "full_sent",
                "unknown" if self.images else "not_applicable",
            )
        if self.full_sent not in ALLOWED_FULL_SENT_STATES:
            raise ValueError("provider_full_sent_state_invalid")
        if self.images and self.full_sent != "unknown":
            raise ValueError("provider_full_sent_requires_receipt")
        if not self.images and self.full_sent != "not_applicable":
            raise ValueError("provider_full_sent_without_images")

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def prompt_body(self) -> str:
        return self.prompt.rendered_body

    @property
    def prompt_key(self) -> str:
        return self.prompt.manifest.prompt_key

    @property
    def prompt_version(self) -> str:
        return self.prompt.manifest.version

    @property
    def prompt_language(self) -> str:
        return self.prompt.manifest.language

    @property
    def prompt_checksum(self) -> str:
        return self.prompt.manifest.prompt_sha256

    @property
    def rendered_sha256(self) -> str:
        return self.prompt.rendered_sha256

    @property
    def image_ordered_sha256(self) -> str | None:
        return ordered_image_sha256(self.images) if self.images else None

@dataclass(frozen=True)
class ProviderResponse:
    provider_request_id: str
    actual_model: str
    output_json: dict[str, Any]
    finish_reason: str
    receipt_json: dict[str, Any]
    raw_output_sha256: str
    parsed_output_sha256: str
    latency_ms: int


class ProviderAdapter(Protocol):
    provider_key: str
    model_name: str

    async def request(self, request: ProviderRequest) -> ProviderResponse: ...


class ProviderNotQualifiedError(RuntimeError):
    """The provider returned an unsafe or non-validation response."""


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        error_class: str,
        message: str = "provider request failed",
        *,
        retryable: bool = False,
        retry_after: float | None = None,
        safe_evidence: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_class = error_class
        self.retryable = retryable
        self.retry_after = retry_after
        # Optional bounded response metadata used by qualification artifacts.
        # It must never contain raw provider output, prompt text, URLs, keys or
        # image bytes; adapters are responsible for constructing this shape.
        self.safe_evidence = safe_evidence or {}
        self.attempts: list[dict[str, Any]] = []


def classify_provider_error(exc: BaseException) -> ProviderRequestError:
    if isinstance(exc, ProviderRequestError):
        return exc
    if isinstance(exc, asyncio.TimeoutError):
        return ProviderRequestError("endpoint_timeout", retryable=True)
    error_class = getattr(exc, "error_class", None)
    if isinstance(error_class, str) and error_class.strip():
        normalized = error_class.strip()
        if normalized not in ALLOWED_PROVIDER_ERROR_CLASSES:
            return ProviderRequestError("provider_unavailable", retryable=False)
        return ProviderRequestError(
            normalized,
            retryable=bool(getattr(exc, "retryable", False)),
            retry_after=getattr(exc, "retry_after", None),
        )
    text = str(exc).casefold()
    if any(marker in text for marker in ("429", "rate limit", "too many", "quota")):
        return ProviderRequestError("rate_limited", retryable=True)
    if any(marker in text for marker in ("connection", "connect", "refused", "reset", "transport")):
        return ProviderRequestError("network_unreachable", retryable=True)
    return ProviderRequestError("provider_unavailable", retryable=False)


__all__ = [
    "ALLOWED_IMAGE_MIME_TYPES",
    "ALLOWED_PROVIDER_ERROR_CLASSES",
    "AIConnectionConfig",
    "AIRequestPolicy",
    "ProviderAdapter",
    "ProviderImageInput",
    "ProviderNotQualifiedError",
    "ProviderRequest",
    "ProviderRequestError",
    "ProviderResponse",
    "classify_provider_error",
    "ordered_image_sha256",
    "sha256_bytes",
]
