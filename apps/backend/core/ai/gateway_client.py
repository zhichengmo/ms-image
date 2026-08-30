from __future__ import annotations

import json
import math
from typing import Any, AsyncIterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx

from apps.backend.core.config import settings


class GatewayResponseParseError(RuntimeError):
    """An HTTP response arrived but could not be normalized as Gateway JSON."""


class GatewayClient:
    """通过 OpenAI 兼容协议调用 ms-ai-platform 的网关客户端。"""

    DEFAULT_TIMEOUT_SECONDS = 120.0
    MAX_TRACE_HEADER_LENGTH = 512
    MAX_API_KEY_LENGTH = 8192

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ):
        if base_url is not None:
            configured_base_url = base_url
            configured_api_key = api_key
            configured_timeout = (
                timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS
            )
            missing_api_key_error = (
                "显式指定 ms-ai-platform Base URL 时必须同时显式传入 api_key"
                if api_key is None
                else None
            )
        else:
            configured_base_url = settings.AI_PLATFORM_OPENAI_BASE_URL
            configured_api_key = (
                api_key if api_key is not None else settings.AI_PLATFORM_API_KEY
            )
            configured_timeout = (
                timeout if timeout is not None else settings.AI_PLATFORM_TIMEOUT_SECONDS
            )
            missing_api_key_error = (
                "ms-ai-platform API Key 未配置：请设置 AI_PLATFORM_API_KEY"
                if api_key is None and not settings.AI_PLATFORM_API_KEY
                else None
            )

        self.base_url = self._normalize_openai_base_url(configured_base_url)
        self.api_key = configured_api_key
        self.timeout = float(configured_timeout)
        self._missing_api_key_error = missing_api_key_error

        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout 必须是大于 0 的有限数值")
        if self.api_key:
            api_key_value = str(self.api_key)
            safe_api_key = self._safe_header_value(
                api_key_value,
                max_length=self.MAX_API_KEY_LENGTH,
            )
            if safe_api_key != api_key_value:
                raise ValueError("api_key 包含非法 Header 字符或长度超限")

    async def chat_completions(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """调用 ms-ai-platform Chat Completions，并校验请求追踪 ID。"""
        if not self.base_url:
            raise RuntimeError(
                "ms-ai-platform 地址未配置：请设置 AI_PLATFORM_OPENAI_BASE_URL"
            )
        if self._missing_api_key_error:
            raise RuntimeError(self._missing_api_key_error)

        headers, outbound_request_id = self._build_request_headers(
            payload,
            idempotency_key=idempotency_key,
            ensure_request_id=True,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            try:
                body = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise GatewayResponseParseError(
                    "provider_response_payload_invalid"
                ) from exc

        if not isinstance(body, dict):
            raise GatewayResponseParseError("provider_response_payload_invalid")

        try:
            request_id = self._resolve_request_id(
                response_headers=response.headers,
                body=body,
                outbound_request_id=outbound_request_id,
            )
        except RuntimeError as exc:
            raise GatewayResponseParseError("provider_request_id_missing") from exc
        return {
            "request_id": request_id,
            "body": body,
        }

    async def stream_chat_completions(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """调用流式 Chat Completions，并产出 metadata/chunk/done 事件。"""
        if not self.base_url:
            raise RuntimeError(
                "ms-ai-platform 地址未配置：请设置 AI_PLATFORM_OPENAI_BASE_URL"
            )
        if self._missing_api_key_error:
            raise RuntimeError(self._missing_api_key_error)

        stream_payload = {**payload, "stream": True}
        headers, outbound_request_id = self._build_request_headers(
            stream_payload,
            idempotency_key=idempotency_key,
            ensure_request_id=True,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=stream_payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                request_id = self._resolve_request_id(
                    response_headers=response.headers,
                    outbound_request_id=outbound_request_id,
                )

                yield {"type": "metadata", "request_id": request_id}
                saw_done = False
                async for data in self._iter_sse_data(response):
                    if data == "[DONE]":
                        saw_done = True
                        yield {"type": "done", "request_id": request_id}
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            "ms-ai-platform 返回了非法 SSE JSON"
                        ) from exc
                    if not isinstance(chunk, dict):
                        raise RuntimeError(
                            "ms-ai-platform SSE data 必须是 JSON 对象"
                        )
                    if chunk.get("error"):
                        error = chunk["error"]
                        message = (
                            error.get("message")
                            if isinstance(error, dict)
                            else str(error)
                        )
                        raise RuntimeError(message or "ms-ai-platform 流式调用失败")
                    yield {
                        "type": "chunk",
                        "request_id": request_id,
                        "data": chunk,
                    }

                if not saw_done:
                    raise RuntimeError("ms-ai-platform 流式响应未以 [DONE] 结束")

    def _build_request_headers(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None,
        ensure_request_id: bool = False,
    ) -> tuple[dict[str, str], str | None]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        if idempotency_key is not None:
            effective_idempotency_key = self._safe_header_value(idempotency_key)
            if effective_idempotency_key is None:
                raise ValueError("显式 Idempotency-Key 包含非法 Header 字符或长度超限")
        else:
            metadata_idempotency_key = metadata.get("idempotency_key")
            effective_idempotency_key = self._safe_header_value(
                metadata_idempotency_key
            )
            if (
                metadata_idempotency_key is not None
                and effective_idempotency_key is None
            ):
                raise ValueError(
                    "metadata.idempotency_key 包含非法 Header 字符或长度超限"
                )
        if effective_idempotency_key is not None:
            headers["Idempotency-Key"] = effective_idempotency_key

        request_id = next(
            (
                safe_value
                for candidate in (
                    metadata.get("request_id"),
                    metadata.get("attempt_id"),
                    metadata.get("task_id"),
                )
                if (safe_value := self._safe_header_value(candidate)) is not None
            ),
            None,
        )
        if request_id is None and ensure_request_id:
            request_id = str(uuid4())
        if request_id is not None:
            headers["X-Request-ID"] = request_id

        trace_id = self._safe_header_value(metadata.get("trace_id"))
        if trace_id is not None:
            headers["X-Trace-ID"] = trace_id
        return headers, request_id

    def _resolve_request_id(
        self,
        *,
        response_headers: httpx.Headers,
        body: dict[str, Any] | None = None,
        outbound_request_id: str | None,
    ) -> str:
        """Resolve a traceable gateway request ID without requiring platform changes.

        A platform-provided correlation ID is preferred.  OpenAI-compatible
        gateways commonly expose it as ``id`` rather than ``request_id``.  If
        neither is present, reuse the ID that this client generated and sent in
        ``X-Request-ID`` so the persisted result remains traceable in this
        service and in any upstream logs that preserve request headers.
        """
        candidates = [response_headers.get("x-request-id")]
        if body is not None:
            candidates.extend((body.get("request_id"), body.get("id")))
        candidates.append(outbound_request_id)

        for candidate in candidates:
            if request_id := self._safe_header_value(candidate):
                return request_id
        raise RuntimeError("无法生成有效的网关 request_id")

    @staticmethod
    async def _iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                if data_lines:
                    yield "\n".join(data_lines)
                    data_lines.clear()
                continue
            if line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if separator and field == "data":
                data_lines.append(value[1:] if value.startswith(" ") else value)
        if data_lines:
            yield "\n".join(data_lines)

    @staticmethod
    def _normalize_openai_base_url(base_url: str) -> str:
        raw_url = base_url.strip()
        if not raw_url:
            return ""

        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Base URL 必须是包含 Host 的绝对 HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Base URL 不允许包含 userinfo")
        if parsed.query or parsed.fragment:
            raise ValueError("Base URL 不允许包含 query 或 fragment")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("Base URL 端口非法") from exc

        path_segments = parsed.path.rstrip("/").split("/")
        while len(path_segments) >= 2 and path_segments[-2:] == ["v1", "v1"]:
            path_segments.pop()
        if not path_segments or path_segments[-1] != "v1":
            path_segments.append("v1")
        normalized_path = "/".join(path_segments)
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"

        return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))

    @staticmethod
    def _safe_header_value(
        value: Any, *, max_length: int = MAX_TRACE_HEADER_LENGTH
    ) -> str | None:
        if value is None:
            return None
        try:
            normalized = str(value).strip()
            normalized.encode("ascii")
        except Exception:
            return None
        if (
            not normalized
            or len(normalized) > max_length
            or any(
                ord(character) < 32 or ord(character) == 127 for character in normalized
            )
        ):
            return None
        return normalized
