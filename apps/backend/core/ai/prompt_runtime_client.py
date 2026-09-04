"""Prompt Runtime client with direct Nacos and legacy HTTP transports."""

from __future__ import annotations

from typing import Any

import httpx

from apps.backend.core.ai.prompt_source import (
    NacosPromptSourceClient,
    PromptSourceError,
    nacos_data_id,
    normalize_imported_prompt,
    parse_nacos_prompt_payload,
    variant_candidates,
)
from apps.backend.core.ai.prompting.contracts import sha256_text
from apps.backend.core.ai.prompting.renderer import PromptRenderError, PromptRenderer
from apps.backend.core.config import settings


class PromptRuntimeClient:
    """Render Prompt content through the configured source transport."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        env: str | None = None,
        caller_service: str | None = None,
        timeout: float | None = None,
        provider: str | None = None,
        nacos_source_client: NacosPromptSourceClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.PROMPT_RUNTIME_URL).rstrip("/")
        self.api_key = (
            api_key if api_key is not None else settings.PROMPT_RUNTIME_API_KEY
        )
        self.env = env or settings.PROMPT_RUNTIME_ENV
        self.caller_service = caller_service or settings.PROMPT_RUNTIME_CALLER_SERVICE
        self.timeout = timeout or settings.PROMPT_RUNTIME_TIMEOUT_SECONDS
        self.provider = (
            provider or settings.PROMPT_RUNTIME_PROVIDER or "nacos"
        ).strip().lower()
        self.nacos_source_client = nacos_source_client

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
        if self.provider == "nacos":
            return await self._render_with_nacos(
                service_code=service_code,
                module_code=module_code,
                prompt_key=prompt_key,
                variables=variables,
                locale=locale,
                variant=variant,
            )
        if self.provider == "http":
            return await self._render_with_http(
                service_code=service_code,
                module_code=module_code,
                prompt_key=prompt_key,
                variables=variables,
                locale=locale,
                variant=variant,
                trace_id=trace_id,
                request_id=request_id,
                user_id=user_id,
            )
        raise RuntimeError(f"不支持的 PROMPT_RUNTIME_PROVIDER: {self.provider}")

    async def _render_with_http(
        self,
        *,
        service_code: str,
        module_code: str,
        prompt_key: str,
        variables: dict[str, Any],
        locale: str,
        variant: str,
        trace_id: str | None,
        request_id: str | None,
        user_id: str | None,
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

    async def _render_with_nacos(
        self,
        *,
        service_code: str,
        module_code: str,
        prompt_key: str,
        variables: dict[str, Any],
        locale: str,
        variant: str,
    ) -> dict[str, Any]:
        requested_variant = variant.strip() if isinstance(variant, str) else ""
        requested_variant = requested_variant or "default"
        source = self.nacos_source_client
        owns_source = source is None
        if source is None:
            namespace_id = (
                settings.NACOS_PROMPT_NAMESPACE_ID
                or settings.NACOS_NAMESPACE_ID
            ).strip()
            source = NacosPromptSourceClient(
                server_addr=settings.NACOS_SERVER_ADDR,
                namespace_id=namespace_id,
                context_path=settings.NACOS_CONTEXT_PATH,
                username=settings.NACOS_USERNAME,
                password=settings.NACOS_PASSWORD,
                timeout_seconds=settings.NACOS_PROMPT_TIMEOUT_SECONDS,
                caller_service=self.caller_service,
            )
        try:
            candidates = variant_candidates(
                requested_variant,
                module_code=module_code,
            )
            for candidate_variant in candidates:
                source_key = nacos_data_id(
                    service_code=service_code,
                    module_code=module_code,
                    prompt_key=prompt_key,
                    variant=candidate_variant,
                    locale=locale,
                )
                payload = await source.fetch(
                    data_id=source_key,
                    version=settings.NACOS_PROMPT_VERSION or None,
                    label=settings.NACOS_PROMPT_LABEL or None,
                )
                if payload is None:
                    continue
                record = parse_nacos_prompt_payload(payload)
                if not record.output_schema:
                    raise RuntimeError(
                        f"Nacos Prompt 缺少 output schema: {source_key}"
                    )
                content, variables_contract = normalize_imported_prompt(
                    record.template
                )
                render_variables = dict(variables)
                render_variables.setdefault("OUTPUT_SCHEMA_JSON", record.output_schema)
                render_variables.setdefault("REPORT_SCHEMA_JSON", record.output_schema)
                required, optional = PromptRenderer.declared_variables(
                    variables_contract
                )
                selected_variables = {
                    name: render_variables[name]
                    for name in required | optional
                    if name in render_variables
                }
                rendered = PromptRenderer.render(
                    content=content,
                    variables_json=variables_contract,
                    safe_variables=selected_variables,
                    max_prompt_chars=120_000,
                )
                fallback_used = candidate_variant != requested_variant
                return {
                    "messages": [
                        {"role": "user", "content": rendered.rendered_text}
                    ],
                    "content": rendered.rendered_text,
                    "rendered_prompt": rendered.rendered_text,
                    "output_schema": record.output_schema,
                    "version_public_id": record.version,
                    "content_hash": record.md5 or sha256_text(record.template),
                    "release_public_id": record.label,
                    "requested_variant": requested_variant,
                    "resolved_variant": candidate_variant,
                    "fallback_used": fallback_used,
                    "metadata": {
                        "source_type": "nacos",
                        "nacos_prompt_key": source_key,
                        "namespace_id": source.namespace_id,
                        "requested_variant": requested_variant,
                        "resolved_variant": candidate_variant,
                        "fallback_used": fallback_used,
                        "rendered_prompt_sha256": rendered.rendered_prompt_sha256,
                        "context_sha256": rendered.context_sha256,
                    },
                }
        except (PromptSourceError, PromptRenderError) as exc:
            raise RuntimeError(str(exc)) from exc
        finally:
            if owns_source:
                await source.aclose()
        tried = ", ".join(
            nacos_data_id(
                service_code=service_code,
                module_code=module_code,
                prompt_key=prompt_key,
                variant=candidate_variant,
                locale=locale,
            )
            for candidate_variant in candidates
        )
        raise RuntimeError(f"当前语言的 Nacos Prompt 尚未发布: {tried}")


__all__ = ["PromptRuntimeClient"]
