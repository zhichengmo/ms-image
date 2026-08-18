"""Shared OpenAI-compatible HTTP transport.

The client knows transport, authentication, status/error mapping and strict
JSON extraction only.  Modality adapters decide prompt/schema semantics and
persist their own ModelCall records.
"""

from __future__ import annotations

import base64
import hashlib
import json
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, APIStatusError

from .contracts import ProviderImageInput, ordered_image_sha256
from .egress_proof import build_adapter_egress_proof, canonical_json_sha256, sha256_text


class ProviderHTTPError(RuntimeError):
    def __init__(
        self,
        error_class: str,
        *,
        retryable: bool,
        retry_after: float | None = None,
        safe_evidence: dict[str, Any] | None = None,
    ):
        super().__init__(error_class)
        self.error_class = error_class
        self.retryable = retryable
        self.retry_after = retry_after
        self.safe_evidence = safe_evidence or {}


class OpenAICompatibleClient:
    _clients: dict[tuple[str, str], AsyncOpenAI] = {}
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        egress_proof_signing_key: str = "",
    ):
        if not base_url.strip() or not api_key.strip() or not model.strip():
            raise ValueError("provider_configuration_incomplete")
        self.base_url = base_url.rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("provider_endpoint_invalid")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.egress_proof_signing_key = egress_proof_signing_key

    def _client(self) -> AsyncOpenAI:
        key = (self.base_url, self.api_key)
        client = self._clients.get(key)
        if client is None:
            client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                max_retries=0,
                timeout=self.timeout_seconds,
            )
            self._clients[key] = client
        return client

    @property
    def endpoint(self) -> str:
        return self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"

    async def complete_json(
        self,
        *,
        prompt: str,
        images: tuple[ProviderImageInput, ...] = (),
        response_schema: dict[str, Any] | None = None,
        request_nonce: str | None = None,
        prompt_sha256: str | None = None,
        rendered_sha256: str | None = None,
        response_schema_sha256: str | None = None,
    ) -> dict[str, Any]:
        if not self.egress_proof_signing_key:
            raise ProviderHTTPError(
                "egress_proof_signing_key_missing", retryable=False
            )
        started = monotonic()
        content: list[dict[str, str]] = [{"type": "text", "text": prompt}]
        for image in images:
            encoded = base64.b64encode(image.content).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image.mime_type};base64,{encoded}",
                    },
                }
            )
        response_format: dict[str, Any] = {"type": "json_object"}
        if response_schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "xray_validation_response",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
            "response_format": response_format,
        }
        try:
            response = await self._client().chat.completions.create(
                **payload,
                extra_headers={"X-Request-Nonce": request_nonce} if request_nonce else None,
                timeout=self.timeout_seconds,
            )
            response_status = 200
            response_headers = {}
            response_content = json.dumps(response.model_dump(), ensure_ascii=False).encode("utf-8")
            body_for_proof = response.model_dump()
        except (APITimeoutError, httpx.TimeoutException) as exc:
            raise ProviderHTTPError("endpoint_timeout", retryable=True) from exc
        except (APIConnectionError, httpx.ConnectError) as exc:
            # Do not expose the endpoint or exception text.  TLS failures are
            # useful operationally but must remain a stable, secret-free class.
            text = str(exc).casefold()
            if any(marker in text for marker in ("ssl", "tls", "certificate", "verify")):
                raise ProviderHTTPError("tls_failure", retryable=False) from exc
            raise ProviderHTTPError("network_unreachable", retryable=True) from exc
        except APIStatusError as exc:
            response_status = int(getattr(exc, "status_code", 500) or 500)
            response_headers = dict(getattr(getattr(exc, "response", None), "headers", {}) or {})
            response_content = b""
            body_for_proof = {}
            if response_status == 429:
                retry_after = None
                try:
                    retry_after = max(0.0, float(response_headers.get("retry-after")))
                except (TypeError, ValueError):
                    pass
                raise ProviderHTTPError("rate_limited", retryable=True, retry_after=retry_after) from exc
            if response_status in {401, 403}:
                raise ProviderHTTPError("provider_auth", retryable=True) from exc
            if response_status == 404:
                raise ProviderHTTPError("model_invalid", retryable=False) from exc
            raise ProviderHTTPError(
                "provider_unavailable" if response_status >= 500 else "schema_invalid",
                retryable=response_status >= 500,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderHTTPError("provider_unavailable", retryable=True) from exc
        latency_ms = max(0, int((monotonic() - started) * 1000))
        choices_for_proof = (
            body_for_proof.get("choices")
            if isinstance(body_for_proof, dict)
            else None
        )
        first_choice = (
            choices_for_proof[0]
            if isinstance(choices_for_proof, list)
            and choices_for_proof
            and isinstance(choices_for_proof[0], dict)
            else {}
        )
        provider_request_id = (
            body_for_proof.get("id") if isinstance(body_for_proof, dict) else None
        )
        actual_model = (
            body_for_proof.get("model") if isinstance(body_for_proof, dict) else None
        )
        egress_proof = build_adapter_egress_proof(
            signing_key=self.egress_proof_signing_key,
            transport_status="qualified" if 200 <= response_status < 300 else "provider_error",
            endpoint_sha256=sha256_text(self.endpoint),
            key_fingerprint=sha256_text(self.api_key),
            requested_model=self.model,
            prompt_sha256=prompt_sha256 or sha256_text(prompt),
            rendered_sha256=rendered_sha256 or sha256_text(prompt),
            schema_sha256=response_schema_sha256
            or canonical_json_sha256(response_schema or {}),
            request_nonce_sha256=sha256_text(request_nonce or ""),
            image_ordered_sha256=ordered_image_sha256(images) if images else None,
            images=[
                {
                    "source_index": image.source_index,
                    "sent_sha256": image.sent_sha256,
                }
                for image in images
            ],
            http_status=response_status,
            provider_request_id_sha256=(
                sha256_text(provider_request_id)
                if isinstance(provider_request_id, str) and provider_request_id
                else None
            ),
            actual_model=(
                actual_model
                if isinstance(actual_model, str) and actual_model.strip()
                else None
            ),
            response_body_sha256=hashlib.sha256(response_content).hexdigest(),
            usage=_safe_usage(
                body_for_proof.get("usage")
                if isinstance(body_for_proof, dict)
                else None
            ),
            finish_reason=str(first_choice.get("finish_reason") or "unknown"),
            latency_ms=latency_ms,
        )
        error_evidence = {"adapter_egress_proof": egress_proof}
        try:
            body = body_for_proof
            choices = body.get("choices")
            content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices else None
            if isinstance(content, list):
                content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
            parsed = json.loads(content) if isinstance(content, str) else None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderHTTPError(
                "schema_invalid", retryable=False, safe_evidence=error_evidence
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderHTTPError(
                "schema_invalid", retryable=False, safe_evidence=error_evidence
            )
        return {
            "provider_request_id": body.get("id"),
            "actual_model": body.get("model"),
            "output_json": parsed,
            "finish_reason": choices[0].get("finish_reason") if choices else "unknown",
            "image_count_received": body.get("image_count_received"),
            "usage": _safe_usage(body.get("usage")),
            "latency_ms": latency_ms,
            "adapter_egress_proof": egress_proof,
            "raw_content": content,
            "image_receipts": _safe_image_receipts(body.get("image_receipts")),
            "receipt_capability_version": (
                body.get("receipt_capability_version")
                if isinstance(body.get("receipt_capability_version"), str)
                else None
            ),
            "received_at": (
                body.get("received_at")
                if isinstance(body.get("received_at"), str)
                else None
            ),
            "receipt_signature": (
                body.get("receipt_signature")
                if isinstance(body.get("receipt_signature"), str)
                else None
            ),
            "request_nonce_echo": (
                body.get("request_nonce_echo")
                if isinstance(body.get("request_nonce_echo"), str)
                else None
            ),
        }


def _safe_image_receipts(value: Any) -> list[dict[str, Any]] | None:
    """Accept only bounded, non-sensitive provider receipt metadata."""
    if not isinstance(value, list):
        return None
    receipts: list[dict[str, Any]] = []
    for item in value[:512]:
        if not isinstance(item, dict):
            return None
        source_index = item.get("source_index")
        sent_sha256 = item.get("sent_sha256")
        status = item.get("status")
        if (
            not isinstance(source_index, int)
            or source_index < 0
            or not isinstance(sent_sha256, str)
            or len(sent_sha256) != 64
            or any(char not in "0123456789abcdef" for char in sent_sha256)
            or not isinstance(status, str)
            or status not in {"confirmed", "unknown", "failed"}
        ):
            return None
        receipts.append(
            {
                "source_index": source_index,
                "sent_sha256": sent_sha256,
                "status": status,
            }
        )
    return receipts


def _safe_usage(value: Any) -> dict[str, int] | None:
    """Keep only bounded token counters from provider-specific usage data."""
    if not isinstance(value, dict):
        return None
    allowed = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
    }
    usage = {
        key: item
        for key, item in value.items()
        if key in allowed and isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 10**9
    }
    return usage or None


__all__ = ["ProviderHTTPError", "OpenAICompatibleClient"]
