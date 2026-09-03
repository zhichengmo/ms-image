"""HTTP Prompt Runtime client aligned with ms-ai-fast's runtime contract."""

from __future__ import annotations

from typing import Any

import httpx

from apps.backend.core.config import settings


class PromptRuntimeClient:
    """调用 ms-ai-platform Prompt Render API 并返回渲染结果。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        env: str | None = None,
        caller_service: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.PROMPT_RUNTIME_URL).rstrip("/")
        self.api_key = (
            api_key if api_key is not None else settings.PROMPT_RUNTIME_API_KEY
        )
        self.env = env or settings.PROMPT_RUNTIME_ENV
        self.caller_service = caller_service or settings.PROMPT_RUNTIME_CALLER_SERVICE
        self.timeout = timeout or settings.PROMPT_RUNTIME_TIMEOUT_SECONDS

    async def render(
        self,
        *,
        service_code: str,
        module_code: str,
        prompt_key: str,
        variables: dict[str, Any],
        locale: str = "zh-CN",
        variant: str = "default",
        trace_id: str | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("PROMPT_RUNTIME_URL 未配置")
        if not self.api_key:
            raise RuntimeError("PROMPT_RUNTIME_API_KEY 未配置")
        payload = {
            "service_code": service_code,
            "module_code": module_code,
            "prompt_key": prompt_key,
            "env": self.env,
            "locale": locale,
            "variant": variant or "default",
            "variables": variables,
            "caller": {
                "service": self.caller_service,
                "request_id": request_id,
                "trace_id": trace_id,
                "user_id": user_id,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/prompts/render",
                json=payload,
                headers={"X-MS-API-Key": self.api_key},
            )
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Prompt runtime 返回格式错误")
        if body.get("success") is False:
            message = body.get("message") or "Prompt 渲染失败"
            error_code = body.get("error_code")
            suffix = f"({error_code})" if error_code else ""
            raise RuntimeError(f"{message}{suffix}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Prompt runtime 返回 data 为空或格式错误")
        return data


__all__ = ["PromptRuntimeClient"]
