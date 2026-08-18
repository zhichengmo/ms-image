"""XRay adapter around the shared external Provider HTTP client."""

from __future__ import annotations

import json
import hashlib
import hmac
from typing import Any

from app.core.ai.contracts import ProviderRequest, ProviderRequestError, ProviderResponse
from app.core.ai.contracts import AIConnectionConfig
from app.core.ai.egress_proof import adapter_egress_proof_is_valid, sha256_text as proof_sha256_text
from app.core.ai.openai_compatible import OpenAICompatibleClient, ProviderHTTPError
from app.core.config import settings
from app.service.ai_governance_service import GovernedConnection
from .prompt_service import sha256_text


class OpenAICompatibleProvider:
    provider_key = "openai/compatible"

    def __init__(
        self,
        *,
        client: OpenAICompatibleClient,
        receipt_signing_key: str = "",
    ):
        self.client = client
        self.model_name = client.model
        self.receipt_signing_key = receipt_signing_key

    async def request(self, request: ProviderRequest) -> ProviderResponse:
        try:
            result = await self.client.complete_json(
                prompt=request.prompt_body,
                images=request.images,
                response_schema=request.response_schema,
                request_nonce=request.request_nonce,
                prompt_sha256=request.prompt_checksum,
                rendered_sha256=request.rendered_sha256,
                response_schema_sha256=request.response_schema_sha256,
            )
        except ProviderHTTPError as exc:
            raise ProviderRequestError(
                exc.error_class,
                retryable=exc.retryable,
                retry_after=exc.retry_after,
                safe_evidence=exc.safe_evidence,
            ) from exc
        egress_proof = result.get("adapter_egress_proof")
        expected_images = [
            {
                "source_index": image.source_index,
                "sent_sha256": image.sent_sha256,
            }
            for image in request.images
        ]
        if not adapter_egress_proof_is_valid(
            egress_proof,
            signing_key=self.client.egress_proof_signing_key,
            expected_transport_status="qualified",
            expected_endpoint_sha256=proof_sha256_text(self.client.endpoint),
            expected_key_fingerprint=proof_sha256_text(self.client.api_key),
            expected_model=request.requested_model,
            expected_prompt_sha256=request.prompt_checksum,
            expected_rendered_sha256=request.rendered_sha256,
            expected_schema_sha256=request.response_schema_sha256,
            expected_request_nonce_sha256=(
                hashlib.sha256(request.request_nonce.encode("utf-8")).hexdigest()
                if request.request_nonce
                else proof_sha256_text("")
            ),
            expected_image_ordered_sha256=request.image_ordered_sha256,
            expected_images=expected_images,
        ):
            raise ProviderRequestError(
                "provider_egress_proof_invalid", retryable=False
            )
        provider_request_id = result.get("provider_request_id")
        if not isinstance(provider_request_id, str) or not provider_request_id:
            raise ProviderRequestError(
                "provider_receipt_missing",
                retryable=False,
                safe_evidence=_safe_response_evidence(result),
            )
        actual_model = result.get("actual_model")
        if not isinstance(actual_model, str) or not actual_model.strip():
            raise ProviderRequestError(
                "model_invalid",
                retryable=False,
                safe_evidence=_safe_response_evidence(result),
            )
        if actual_model != request.requested_model:
            raise ProviderRequestError(
                "model_mismatch",
                retryable=False,
                safe_evidence=_safe_response_evidence(result),
            )
        output_json = result["output_json"]
        encoded = json.dumps(output_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        raw_content = result.get("raw_content")
        image_receipts = result.get("image_receipts")
        if request.images:
            image_count_received = result.get("image_count_received")
            receipt_capability_absent = all(
                result.get(key) is None or result.get(key) == ""
                for key in (
                    "image_count_received",
                    "image_receipts",
                    "receipt_capability_version",
                    "request_nonce_echo",
                    "received_at",
                    "receipt_signature",
                )
            )
            receipt_invalid = (
                type(image_count_received) is not int
                or image_count_received != len(request.images)
                or result.get("request_nonce_echo") != request.request_nonce
                or result.get("receipt_capability_version")
                != "provider-image-receipt.v1"
                or not isinstance(result.get("received_at"), str)
                or not result["received_at"].strip()
                or not _receipts_confirm_images(image_receipts, request)
                or not _receipt_signature_valid(
                    result,
                    request,
                    image_receipts,
                    self.receipt_signing_key,
                )
            )
            if receipt_invalid and not receipt_capability_absent:
                raise ProviderRequestError(
                    "provider_receipt_missing",
                    retryable=False,
                    safe_evidence=_safe_response_evidence(
                        result,
                        expected_image_count=len(request.images),
                        expected_ordered_sha256=request.image_ordered_sha256,
                    ),
                )
            if receipt_capability_absent:
                image_receipts = []
                receipt_status = "unsupported"
                full_sent = "unknown"
                coverage_status = "egress_proven"
            else:
                receipt_status = "confirmed"
                full_sent = "confirmed"
                coverage_status = "full_sent"
        else:
            image_receipts = []
            image_count_received = 0
            receipt_status = "not_applicable"
            full_sent = "not_applicable"
            coverage_status = "not_applicable"
        return ProviderResponse(
            provider_request_id=provider_request_id,
            actual_model=actual_model,
            output_json=output_json,
            finish_reason=str(result.get("finish_reason") or "unknown"),
            receipt_json={
                "provider_request_id_sha256": egress_proof.get(
                    "provider_request_id_sha256"
                ),
                "provider_key": self.provider_key,
                "actual_model": actual_model,
                "status": receipt_status,
                "transport_status": "qualified",
                "coverage_status": coverage_status,
                "image_count_received": image_count_received,
                "image_receipts": image_receipts,
                "image_ordered_sha256": request.image_ordered_sha256,
                "full_sent": full_sent,
                "receipt_capability_version": (
                    "provider-image-receipt.v1"
                    if receipt_status == "confirmed"
                    else None
                ),
                "received_at": result.get("received_at"),
                "receipt_signature_verified": (
                    bool(self.receipt_signing_key)
                    if receipt_status == "confirmed"
                    else False
                ),
                "request_nonce_sha256": hashlib.sha256(
                    request.request_nonce.encode("utf-8")
                ).hexdigest() if request.request_nonce else None,
                "usage": result.get("usage"),
                "adapter_egress_proof": egress_proof,
            },
            raw_output_sha256=sha256_text(raw_content if isinstance(raw_content, str) else encoded),
            parsed_output_sha256=sha256_text(encoded),
            latency_ms=int(result.get("latency_ms") or 0),
        )


def _safe_response_evidence(
    result: dict[str, Any],
    *,
    expected_image_count: int | None = None,
    expected_ordered_sha256: str | None = None,
) -> dict[str, Any]:
    """Project response facts safe for a blocked qualification artifact."""
    evidence: dict[str, Any] = {
        "actual_model": result.get("actual_model"),
        "finish_reason": str(result.get("finish_reason") or "unknown")[:64],
        "latency_ms": result.get("latency_ms"),
        "provider_request_id_present": bool(result.get("provider_request_id")),
        "image_count_received": result.get("image_count_received"),
        "image_receipt_count": (
            len(result["image_receipts"])
            if isinstance(result.get("image_receipts"), list)
            else 0
        ),
        "receipt_capability_version": result.get("receipt_capability_version"),
        "request_nonce_echo_present": bool(result.get("request_nonce_echo")),
        "received_at_present": bool(result.get("received_at")),
        "receipt_signature_present": bool(result.get("receipt_signature")),
        "usage": result.get("usage") if isinstance(result.get("usage"), dict) else None,
    }
    egress_proof = result.get("adapter_egress_proof")
    if isinstance(egress_proof, dict):
        evidence["adapter_egress_proof"] = egress_proof
    raw_content = result.get("raw_content")
    if isinstance(raw_content, str):
        evidence["raw_output_sha256"] = hashlib.sha256(
            raw_content.encode("utf-8")
        ).hexdigest()
    output_json = result.get("output_json")
    if isinstance(output_json, dict):
        encoded = json.dumps(
            output_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        evidence["parsed_output_sha256"] = hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest()
    request_id = result.get("provider_request_id")
    if isinstance(request_id, str) and request_id:
        evidence["provider_request_id_sha256"] = hashlib.sha256(
            request_id.encode("utf-8")
        ).hexdigest()
    if expected_image_count is not None:
        evidence["expected_image_count"] = expected_image_count
    if expected_ordered_sha256 is not None:
        evidence["expected_ordered_sha256"] = expected_ordered_sha256
    return evidence


def _receipts_confirm_images(value: Any, request: ProviderRequest) -> bool:
    if not isinstance(value, list) or len(value) != len(request.images):
        return False
    expected = {
        image.source_index: image.sent_sha256 for image in request.images
    }
    received: dict[int, str] = {}
    for item in value:
        if not isinstance(item, dict) or item.get("status") != "confirmed":
            return False
        source_index = item.get("source_index")
        sent_sha256 = item.get("sent_sha256")
        if (
            type(source_index) is not int
            or not isinstance(sent_sha256, str)
            or len(sent_sha256) != 64
            or any(char not in "0123456789abcdef" for char in sent_sha256)
        ):
            return False
        if source_index in received:
            return False
        received[source_index] = sent_sha256
    return received == expected


def _receipt_signature_valid(
    result: dict[str, Any],
    request: ProviderRequest,
    image_receipts: Any,
    signing_key: str,
) -> bool:
    signature = result.get("receipt_signature")
    if (
        not signing_key
        or not isinstance(signature, str)
        or len(signature) != 64
        or any(char not in "0123456789abcdef" for char in signature)
    ):
        return False
    payload = {
        "request_nonce": request.request_nonce,
        "provider_request_id": result.get("provider_request_id"),
        "actual_model": result.get("actual_model"),
        "image_count_received": result.get("image_count_received"),
        "image_receipts": image_receipts,
        "receipt_capability_version": result.get("receipt_capability_version"),
        "received_at": result.get("received_at"),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected = hmac.new(
        signing_key.encode("utf-8"), canonical, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def governed_provider_pool(governed_connections: tuple[GovernedConnection, ...]) -> tuple[
    list[AIConnectionConfig],
    dict[str, OpenAICompatibleProvider],
    dict[str, str],
]:
    """Build the OpenAI-compatible adapter pool from DB-governed lanes."""
    connections: list[AIConnectionConfig] = []
    providers: dict[str, OpenAICompatibleProvider] = {}
    key_fingerprints: dict[str, str] = {}
    for governed in governed_connections:
        connection_id = governed.connection_id
        connections.append(
            AIConnectionConfig(
                connection_id=connection_id,
                family="openai-compatible",
                base_url=governed.base_url,
                model=governed.model,
                api_key_ref=governed.secret_ref,
                cooldown_seconds=governed.cooldown_seconds,
            )
        )
        providers[connection_id] = OpenAICompatibleProvider(
            client=OpenAICompatibleClient(
                base_url=governed.base_url,
                api_key=governed.api_key,
                model=governed.model,
                timeout_seconds=governed.timeout_seconds,
                max_output_tokens=governed.max_tokens,
                egress_proof_signing_key=settings.AI_EGRESS_PROOF_SIGNING_KEY,
            ),
            receipt_signing_key=settings.AI_RECEIPT_SIGNING_KEY,
        )
        key_fingerprints[connection_id] = hashlib.sha256(governed.api_key.encode("utf-8")).hexdigest()
    return connections, providers, key_fingerprints


__all__ = [
    "OpenAICompatibleProvider",
    "governed_provider_pool",
]
