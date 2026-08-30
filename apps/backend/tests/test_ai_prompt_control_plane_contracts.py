"""Offline contracts for the provider-disabled AI Prompt control plane.

These tests intentionally do not construct sessions or contact MySQL, Redis,
Secret Manager, OSS, RabbitMQ, or a Provider.  They guard the pure contracts
that make Config v2 reproducible before Phase D enables a real Provider.
"""

from __future__ import annotations

import ast
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from apps.backend.core.ai.config_contract import (
    TASK_REQUEST_SNAPSHOT_V2,
    activation_slot_sha256,
    legacy_activation_slot,
)
from apps.backend.core.ai.connection_contract import (
    ConnectionContractError,
    canonical_connection_metadata_sha256,
    canonicalize_connection_base_url,
)
from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    normalize_gateway_profile,
)
from apps.backend.core.ai.prompting.message_contract import (
    PROMPT_MESSAGE_CONTRACT_V1,
    PromptMessageAssembler,
    validate_prompt_message_template,
)
from apps.backend.core.ai.prompting import PromptContractError
from apps.backend.core.ai.prompting.contracts import sha256_json, sha256_text
from apps.backend.core.ai.prompting.renderer import PromptRenderError, PromptRenderer
from apps.backend.core.pipeline import build_default_registry
from apps.backend.core.config import Settings
from apps.backend.schemas.ai_config import AIConfigCreate, AIConfigResponse
from apps.backend.schemas.ai_control import (
    BudgetPolicyContract,
    ConnectionCreate,
    ConnectionResponse,
    GatewayProfileContract,
    GenerationParams,
    ModelPoolLanePlanContract,
    PromptImportRequest,
    PromptVariablesContract,
)
from apps.backend.services.ai_control.service.ai_config_service import AIConfigService
from apps.backend.services.ai_control.service.config_compiler import AIConfigCompiler
from apps.backend.services.ai_control.service.errors import AIControlValidationError
from apps.backend.services.ai_control.service.prompt_import_service import (
    PromptImportService,
)
from apps.backend.services.ai_control.service.prompt_template_service import (
    PromptTemplateService,
)
from apps.backend.services.ai_control.service.prompt_source import (
    PromptSourceError,
    PromptSourceUnsafeError,
    build_source_receipt,
    nacos_data_id,
    normalize_imported_prompt,
    receipt_sha256,
    variant_candidates,
)
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_primary_ai_request_command,
    build_targeted_ai_request_command,
)


VALID_VARIABLES = {
    "contract_version": "prompt-variables.v1",
    "required": ["SAFE_STUDY_CONTEXT_JSON", "OUTPUT_SCHEMA_JSON"],
    "optional": ["PRIMARY_RESULT_JSON"],
}

VALID_LANE = {
    "lane_key": "primary",
    "priority": 1,
    "connection_id": "connection_v1",
    "connection_sha256": "a" * 64,
    "requested_model": "provider-model",
    "timeout_ms": 60_000,
    "max_attempts": 1,
    "generation_params": {
        "temperature": 0.1,
        "top_p": 1.0,
        "max_output_tokens": 4096,
    },
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _connection_metadata(*, base_url: str) -> dict[str, Any]:
    return {
        "connection_key": "xray_provider",
        "version": "v1",
        "provider_type": "openai_compatible",
        "api_format": "responses",
        "base_url": base_url,
        "region": "provider-region",
        "capability_json": {
            "contract_version": "connection-capability.v1",
            "supports_images": True,
        },
    }


def _assert_no_sensitive_keys(value: Any) -> None:
    forbidden = (
        "secret",
        "token",
        "authorization",
        "password",
        "api_key",
        "credential",
    )
    if isinstance(value, dict):
        assert not any(
            marker in key.casefold() for key in value for marker in forbidden
        )
        for nested in value.values():
            _assert_no_sensitive_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_sensitive_keys(nested)


def test_control_plane_jwt_readiness_rejects_placeholder_secret(monkeypatch) -> None:
    from apps.backend.core import dependencies

    monkeypatch.setattr(dependencies.settings, "ADMIN_ALGORITHM", "HS256")
    monkeypatch.setattr(dependencies.settings, "ADMIN_SECRET_KEY", "change-me")

    assert dependencies.control_plane_jwt_readiness() == (
        False,
        "control_plane_jwt_key_unavailable",
    )


@pytest.mark.anyio
async def test_ai_control_readiness_uses_only_required_dependencies(
    monkeypatch,
) -> None:
    from apps.backend.services.ai_control import readiness

    async def database_ready() -> tuple[bool, str | None]:
        return True, None

    monkeypatch.setattr(readiness.settings, "NACOS_SERVER_ADDR", "")
    monkeypatch.setattr(readiness, "_database_ready", database_ready)
    monkeypatch.setattr(
        readiness,
        "control_plane_jwt_readiness",
        lambda: (True, None),
    )

    result = await readiness.build_ai_control_readiness()

    assert result.ready is True
    assert result.readiness_scope == "ai_control"
    assert result.components.database.ready is True
    assert result.components.control_plane_jwt.ready is True
    assert result.components.nacos.required is False
    assert result.components.nacos.ready is None
    assert set(result.components.model_dump()) == {
        "database",
        "control_plane_jwt",
        "nacos",
    }


@pytest.mark.anyio
async def test_nacos_readiness_uses_prompt_client_capability_probe() -> None:
    from apps.backend.services.ai_control.service.prompt_source import (
        NacosPromptSourceClient,
    )

    calls: list[tuple[str, str, dict[str, str], str]] = []

    class FakeResponse:
        status_code = 200
        headers = {"allow": "GET,HEAD,OPTIONS"}

    class FakeNacosClient:
        async def request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, str],
            response_mode: str,
        ) -> FakeResponse:
            calls.append((method, path, params, response_mode))
            return FakeResponse()

    source = NacosPromptSourceClient(
        server_addr="https://nacos.example",
        namespace_id="prompt-namespace",
        client=FakeNacosClient(),
    )

    await source.check_prompt_api_readiness()

    assert calls == [
        (
            "OPTIONS",
            "/v3/client/ai/prompt",
            {"namespaceId": "prompt-namespace"},
            "response",
        )
    ]


@pytest.mark.anyio
async def test_nacos_readiness_rejects_route_without_prompt_get() -> None:
    from apps.backend.services.ai_control.service.prompt_source import (
        NacosPromptSourceClient,
        PromptSourceError,
    )

    class FakeResponse:
        status_code = 200
        headers = {"allow": "HEAD,OPTIONS"}

    class FakeNacosClient:
        async def request(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse()

    source = NacosPromptSourceClient(
        server_addr="https://nacos.example",
        namespace_id="prompt-namespace",
        client=FakeNacosClient(),
    )

    with pytest.raises(
        PromptSourceError,
        match="prompt_source_nacos_prompt_api_unavailable",
    ):
        await source.check_prompt_api_readiness()


@pytest.mark.anyio
async def test_ai_control_readiness_endpoint_returns_503(monkeypatch) -> None:
    from apps.backend.schemas.ai_control import (
        AIControlReadinessComponent,
        AIControlReadinessComponents,
        AIControlReadinessResponse,
    )
    from apps.backend.services.ai_control.api.api_v1.endpoints import health

    unavailable = AIControlReadinessResponse(
        ready=False,
        readiness_scope="ai_control",
        components=AIControlReadinessComponents(
            database=AIControlReadinessComponent(
                required=True,
                ready=False,
                state="unavailable",
                error="database_unavailable",
            ),
            control_plane_jwt=AIControlReadinessComponent(
                required=True,
                ready=True,
                state="ready",
            ),
            nacos=AIControlReadinessComponent(
                required=False,
                ready=None,
                state="disabled",
            ),
        ),
    )

    async def build_unavailable() -> AIControlReadinessResponse:
        return unavailable

    monkeypatch.setattr(health, "build_ai_control_readiness", build_unavailable)

    response = await health.readiness_check()

    assert response.status_code == 503
    assert b'"success":false' in response.body
    assert b'"readiness_scope":"ai_control"' in response.body


def test_connection_url_is_canonical_and_metadata_hash_is_stable() -> None:
    assert (
        canonicalize_connection_base_url("https://Provider.Example:443/v1/")
        == "https://provider.example/v1"
    )
    assert (
        canonicalize_connection_base_url("http://Platform.Example:80/api/v1/")
        == "http://platform.example/api/v1"
    )
    assert canonical_connection_metadata_sha256(
        _connection_metadata(base_url="https://Provider.Example:443/v1/")
    ) == canonical_connection_metadata_sha256(
        _connection_metadata(base_url="https://provider.example/v1")
    )
    assert canonical_connection_metadata_sha256(
        _connection_metadata(base_url="http://Platform.Example:80/api/v1/")
    ) == canonical_connection_metadata_sha256(
        _connection_metadata(base_url="http://platform.example/api/v1")
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://provider.example/v1",
        "https://user@provider.example/v1",
        "https://provider.example/v1?api_key=unsafe",
        "https://provider.example/v1#fragment",
    ],
)
def test_connection_url_rejects_unsafe_shapes(base_url: str) -> None:
    with pytest.raises(ConnectionContractError, match="ai_connection_base_url_invalid"):
        canonicalize_connection_base_url(base_url)


def test_connection_create_rejects_legacy_secret_reference_input() -> None:
    with pytest.raises(ValidationError):
        ConnectionCreate.model_validate(
            {
                "request_id": "request-1",
                **_connection_metadata(base_url="https://provider.example/v1"),
                "name": "XRay Platform",
                "secret_ref": "secret-manager://legacy/provider",
            }
        )


def test_renderer_is_deterministic_for_frozen_content_and_safe_context() -> None:
    content = (
        "\ufeff请只输出符合 Schema 的结果。\r\n"
        "上下文：{{ SAFE_STUDY_CONTEXT_JSON | tojson }}\n"
        "Schema：{{ OUTPUT_SCHEMA_JSON | tojson }}\n"
        "Primary：{{ PRIMARY_RESULT_JSON | tojson }}\r"
    )
    first = PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "PRIMARY_RESULT_JSON": {"summary": "stable"},
            "OUTPUT_SCHEMA_JSON": {"required": ["result"], "type": "object"},
            "SAFE_STUDY_CONTEXT_JSON": {"study_id": "study_1", "views": ["VD", "LL"]},
        },
        max_prompt_chars=10_000,
    )
    second = PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"study_id": "study_1", "views": ["VD", "LL"]},
            "OUTPUT_SCHEMA_JSON": {"required": ["result"], "type": "object"},
            "PRIMARY_RESULT_JSON": {"summary": "stable"},
        },
        max_prompt_chars=10_000,
    )

    assert first == second
    assert "\r" not in first.rendered_text
    assert "{{" not in first.rendered_text
    assert (
        first.rendered_prompt_sha256
        == PromptRenderer.render(
            content=content,
            variables_json=VALID_VARIABLES,
            safe_variables={
                "SAFE_STUDY_CONTEXT_JSON": {
                    "study_id": "study_1",
                    "views": ["VD", "LL"],
                },
                "OUTPUT_SCHEMA_JSON": {"required": ["result"], "type": "object"},
                "PRIMARY_RESULT_JSON": {"summary": "stable"},
            },
            max_prompt_chars=10_000,
        ).rendered_prompt_sha256
    )


def test_renderer_preserves_literal_dollars_in_jinja_injected_json() -> None:
    rendered = PromptRenderer.render(
        content=(
            "上下文：{{ SAFE_STUDY_CONTEXT_JSON | tojson }}\n"
            "Schema：{{ OUTPUT_SCHEMA_JSON | tojson }}"
        ),
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"note": "literal $value remains data"},
            "OUTPUT_SCHEMA_JSON": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
            },
            "PRIMARY_RESULT_JSON": {"summary": "unused but required by contract"},
        },
        max_prompt_chars=10_000,
    )

    assert '"$schema"' in rendered.rendered_text
    assert "literal $value remains data" in rendered.rendered_text


@pytest.mark.parametrize(
    ("content", "variables_json", "safe_variables", "max_prompt_chars", "error"),
    [
        (
            "{{ SAFE_STUDY_CONTEXT_JSON }}",
            VALID_VARIABLES,
            {"SAFE_STUDY_CONTEXT_JSON": {}},
            100,
            "prompt_required_variable_missing",
        ),
        (
            "{{ SAFE_STUDY_CONTEXT_JSON }}",
            VALID_VARIABLES,
            {
                "SAFE_STUDY_CONTEXT_JSON": {},
                "OUTPUT_SCHEMA_JSON": {},
                "UNDECLARED": {},
            },
            100,
            "prompt_variable_not_declared",
        ),
        (
            "{{ PRIMARY_RESULT_JSON }}",
            VALID_VARIABLES,
            {
                "SAFE_STUDY_CONTEXT_JSON": {},
                "OUTPUT_SCHEMA_JSON": {},
            },
            100,
            "prompt_template_render_failed",
        ),
        (
            "{{ SAFE_STUDY_CONTEXT_JSON }",
            VALID_VARIABLES,
            {"SAFE_STUDY_CONTEXT_JSON": {}, "OUTPUT_SCHEMA_JSON": {}},
            100,
            "prompt_template_invalid",
        ),
        (
            "{{ SAFE_STUDY_CONTEXT_JSON }}",
            VALID_VARIABLES,
            {"SAFE_STUDY_CONTEXT_JSON": {"large": "x" * 100}, "OUTPUT_SCHEMA_JSON": {}},
            10,
            "prompt_rendered_length_invalid",
        ),
    ],
)
def test_renderer_fails_closed_for_invalid_variables_syntax_and_budget(
    content: str,
    variables_json: dict[str, Any],
    safe_variables: dict[str, Any],
    max_prompt_chars: int,
    error: str,
) -> None:
    with pytest.raises(PromptRenderError, match=error):
        PromptRenderer.render(
            content=content,
            variables_json=variables_json,
            safe_variables=safe_variables,
            max_prompt_chars=max_prompt_chars,
        )


def test_renderer_tojson_matches_ms_ai_fast_json_semantics() -> None:
    rendered = PromptRenderer.render(
        content="{{ SAFE_STUDY_CONTEXT_JSON | tojson }} {{ OUTPUT_SCHEMA_JSON | tojson }}",
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"z": "中文", "a": 1},
            "OUTPUT_SCHEMA_JSON": {},
        },
        max_prompt_chars=1_000,
    )

    assert rendered.rendered_text == '{"z": "中文", "a": 1} {}'


def test_renderer_allows_nested_json_context_that_ends_in_double_brace() -> None:
    content = "输出：{{ SAFE_STUDY_CONTEXT_JSON }}，Schema：{{ OUTPUT_SCHEMA_JSON }}"
    rendered = PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"a": {"b": 1}},
            "OUTPUT_SCHEMA_JSON": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
            },
        },
        max_prompt_chars=10_000,
    )
    assert rendered.rendered_prompt_sha256
    assert "prompt_placeholder_unresolved" not in rendered.rendered_text


def test_renderer_supports_dollar_placeholder_as_alias() -> None:
    content = "检查上下文：$SAFE_STUDY_CONTEXT_JSON，Schema：$OUTPUT_SCHEMA_JSON"
    rendered = PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"study_id": "study_1"},
            "OUTPUT_SCHEMA_JSON": {"type": "object"},
        },
        max_prompt_chars=10_000,
    )
    assert '"study_id"' in rendered.rendered_text
    assert '"type"' in rendered.rendered_text
    assert "$" not in rendered.rendered_text


def test_renderer_supports_declared_business_dollar_variable_and_rejects_undeclared() -> (
    None
):
    rendered = PromptRenderer.render(
        content="$base_info",
        variables_json={
            "contract_version": "prompt-variables.v1",
            "required": ["base_info"],
            "optional": [],
        },
        safe_variables={"base_info": {"study_id": "s"}},
        max_prompt_chars=10_000,
    )
    assert rendered.rendered_text == '{"study_id": "s"}'

    with pytest.raises(PromptRenderError, match="prompt_placeholder_undeclared"):
        PromptRenderer.render(
            content="$UNDECLARED_VARIABLE",
            variables_json=VALID_VARIABLES,
            safe_variables={"SAFE_STUDY_CONTEXT_JSON": {}, "OUTPUT_SCHEMA_JSON": {}},
            max_prompt_chars=10_000,
        )


def test_renderer_allows_literal_json_example_in_template_body() -> None:
    content = (
        '输出示例：{"recg": {"photo": "皮肤图"}}\n'
        "上下文：{{ SAFE_STUDY_CONTEXT_JSON }}"
    )
    rendered = PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"study_id": "s"},
            "OUTPUT_SCHEMA_JSON": {},
        },
        max_prompt_chars=10_000,
    )
    assert "皮肤图" in rendered.rendered_text
    assert "SAFE_STUDY_CONTEXT_JSON" not in rendered.rendered_text


def test_activation_slot_is_fixed_and_distinct_from_v1_legacy_slot() -> None:
    common = {
        "config_key": "xray.primary",
        "modality_type": "xray",
        "task_type": "analysis",
        "activation_scope": "global",
        "scope_key": "global",
    }
    slot = activation_slot_sha256(**common)
    assert slot == activation_slot_sha256(**common)
    assert len(slot) == 64
    assert slot != activation_slot_sha256(**{**common, "task_type": "review"})
    assert slot != legacy_activation_slot(**common)
    assert (
        legacy_activation_slot(**common) == "xray.primary:global:global:xray:analysis"
    )


def test_control_plane_json_contracts_accept_prompt_variables_and_reject_unsupported_lanes() -> (
    None
):
    variables = PromptVariablesContract(required=["base_info", "ARBITRARY"])
    assert variables.required == ["base_info", "ARBITRARY"]

    with pytest.raises(ValidationError, match="prompt_variables_contract_invalid"):
        PromptVariablesContract(required=["invalid-name"])

    with pytest.raises(
        ValidationError, match="model_pool_single_primary_lane_required"
    ):
        ModelPoolLanePlanContract(lanes=[{**VALID_LANE, "lane_key": "secondary"}])

    with pytest.raises(ValidationError):
        ModelPoolLanePlanContract(lanes=[VALID_LANE, VALID_LANE])

    with pytest.raises(ValidationError):
        GenerationParams(
            temperature=0.1,
            top_p=1.0,
            max_output_tokens=4096,
            provider_specific_override=True,
        )

    with pytest.raises(ValidationError, match="ai_budget_reserve_before_send_required"):
        BudgetPolicyContract(
            max_prompt_chars=30_000,
            max_input_images=20,
            max_total_calls=1,
            max_total_attempts=1,
            task_deadline_ms=120_000,
            reserve_before_send=False,
        )

    with pytest.raises(ValidationError, match="ai_budget_attempts_less_than_calls"):
        BudgetPolicyContract(
            max_prompt_chars=30_000,
            max_input_images=20,
            max_total_calls=2,
            max_total_attempts=1,
            task_deadline_ms=120_000,
            reserve_before_send=True,
        )


def test_control_plane_responses_do_not_expose_raw_snapshots_or_secret_references() -> (
    None
):
    assert not any(
        "secret" in field.casefold() for field in ConnectionResponse.model_fields
    )
    assert {
        "prompt_content",
        "prompt_variables_json",
        "model_snapshot_json",
        "output_schema_json",
        "compiled_pipeline_json",
    }.isdisjoint(AIConfigResponse.model_fields)

    redacted = AIConfigService._safe_mapping(
        {
            "safe": "value",
            "secret_ref": "secret-manager://private",
            "nested": [
                {"api_key": "never-return", "allowed": 1},
                {"authorization_header": "never-return", "token_count": 7},
            ],
        }
    )
    assert redacted == {"safe": "value", "nested": [{"allowed": 1}, {}]}
    _assert_no_sensitive_keys(redacted)


def test_gateway_profile_disabled_default_and_qualification_contract() -> None:
    default = normalize_gateway_profile(None)
    assert default["provider_enabled"] is False
    assert default["qualification_status"] == "disabled"
    assert default["streaming_mode"] == "json"
    with pytest.raises(
        GatewayContractError, match="gateway_profile_qualification_required"
    ):
        normalize_gateway_profile(
            {
                "contract_version": "ai-gateway-profile.v1",
                "adapter_key": "openai-compatible",
                "provider_enabled": True,
                "qualification_status": "disabled",
                "streaming_mode": "json",
                "image_url_ttl_seconds": 300,
                "allowed_actual_models": ["provider-model"],
            }
        )
    qualified = normalize_gateway_profile(
        {
            "contract_version": "ai-gateway-profile.v1",
            "adapter_key": "openai-compatible",
            "provider_enabled": True,
            "qualification_status": "qualified",
            "streaming_mode": "aggregate_sse",
            "image_url_ttl_seconds": 120,
            "allowed_actual_models": ["provider-model-b", "provider-model-a"],
        }
    )
    assert qualified["allowed_actual_models"] == [
        "provider-model-a",
        "provider-model-b",
    ]
    assert qualified["streaming_mode"] == "aggregate_sse"
    with pytest.raises(
        GatewayContractError, match="gateway_profile_actual_models_required"
    ):
        normalize_gateway_profile(
            {
                "contract_version": "ai-gateway-profile.v1",
                "adapter_key": "openai-compatible",
                "provider_enabled": True,
                "qualification_status": "qualified",
                "streaming_mode": "json",
                "image_url_ttl_seconds": 300,
                "allowed_actual_models": [],
            }
        )
    with pytest.raises(ValidationError, match="gateway_profile_actual_models_required"):
        GatewayProfileContract(
            provider_enabled=True,
            qualification_status="qualified",
            allowed_actual_models=[],
        )


def test_prompt_message_assembler_legacy_and_v1_contracts() -> None:
    legacy = PromptMessageAssembler.assemble(
        rendered_text="单正文",
        message_contract_json=None,
        safe_variables={"SAFE_STUDY_CONTEXT_JSON": {"study_id": "s1"}},
    )
    assert legacy.messages_json == [{"role": "user", "content": "单正文"}]
    assert legacy.contract_version is None

    v1 = PromptMessageAssembler.assemble(
        rendered_text="角色与边界",
        message_contract_json={
            "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
            "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
        },
        safe_variables={"SAFE_STUDY_CONTEXT_JSON": {"study_id": "s1"}},
    )
    assert v1.contract_version == PROMPT_MESSAGE_CONTRACT_V1
    assert v1.messages_json == [{"role": "user", "content": "角色与边界"}]

    without_context = PromptMessageAssembler.assemble(
        rendered_text="角色与边界",
        message_contract_json={
            "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
            "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
        },
        safe_variables={},
    )
    assert without_context.messages_json == [{"role": "user", "content": "角色与边界"}]


def test_prompt_source_data_id_and_variant_fallback_order() -> None:
    assert (
        nacos_data_id(
            service_code="ms",
            module_code="image_recognition",
            prompt_key="xray_primary",
            variant="default",
            locale="zh-CN",
        )
        == "ms.ai-pic.xray-primary.default.zh-CN"
    )
    assert variant_candidates("v2") == ["v2", "default"]
    assert variant_candidates("default") == ["default"]


def test_prompt_source_xray_uses_exact_primary_coordinates() -> None:
    coordinates = (
        ("xray_primary", "common"),
        ("xray_cat_primary", "cat"),
        ("xray_dog_primary", "dog"),
    )
    for prompt_key, variant in coordinates:
        assert nacos_data_id(
            service_code="ms-image",
            module_code="xray",
            prompt_key=prompt_key,
            variant=variant,
            locale="zh-CN",
        ) == f"ms-image.x-ray.primary.{variant}.zh-CN"
        assert variant_candidates(variant, module_code="xray") == [variant]

    for invalid_variant in ("default", "rabbit"):
        with pytest.raises(
            PromptSourceError, match="prompt_source_xray_variant_invalid"
        ):
            variant_candidates(invalid_variant, module_code="xray")

    for prompt_key, wrong_variant in (
        ("xray_primary", "cat"),
        ("xray_cat_primary", "dog"),
        ("xray_dog_primary", "common"),
    ):
        with pytest.raises(
            PromptSourceError, match="prompt_source_xray_variant_mismatch"
        ):
            nacos_data_id(
                service_code="ms-image",
                module_code="xray",
                prompt_key=prompt_key,
                variant=wrong_variant,
                locale="zh-CN",
            )
    with pytest.raises(
        PromptSourceError, match="prompt_source_xray_prompt_key_invalid"
    ):
        nacos_data_id(
            service_code="ms-image",
            module_code="xray",
            prompt_key="xray_rabbit_primary",
            variant="common",
            locale="zh-CN",
        )


def test_species_primary_prompt_assets_preserve_v2_rendering_contract() -> None:
    prompt_root = Path(__file__).resolve().parents[3] / "prompts/xray/nacos/primary"
    common = (
        prompt_root
        / "common/zh-CN/ms-image.x-ray.primary.common.zh-CN.v2.0.0.txt"
    ).read_text()
    common_normalized, common_variables = normalize_imported_prompt(common)
    message_contract = {
        "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
        "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
    }
    rendered_sha256: set[str] = set()

    for species in ("cat", "dog"):
        content = (
            prompt_root
            / species
            / "zh-CN"
            / f"ms-image.x-ray.primary.{species}.zh-CN.v3.0.0.md"
        ).read_text()
        normalized, variables = normalize_imported_prompt(content)
        assert variables == common_variables
        assert set(variables["required"]) == {
            "SAFE_STUDY_CONTEXT_JSON",
            "OUTPUT_SCHEMA_JSON",
        }
        assert "PRIMARY_RESULT_JSON" not in variables["required"]
        validate_prompt_message_template(
            content=normalized,
            message_contract_json=message_contract,
        )
        safe_variables = {
            "SAFE_STUDY_CONTEXT_JSON": {"species": species},
            "OUTPUT_SCHEMA_JSON": {"type": "object"},
        }
        rendered = PromptRenderer.render(
            content=normalized,
            variables_json=variables,
            safe_variables=safe_variables,
            max_prompt_chars=100_000,
        )
        messages = PromptMessageAssembler.assemble(
            rendered_text=rendered.rendered_text,
            message_contract_json=message_contract,
            safe_variables=safe_variables,
        )
        assert messages.messages_json == [
            {"role": "user", "content": rendered.rendered_text}
        ]
        rendered_sha256.add(rendered.rendered_prompt_sha256)

    assert common_normalized
    assert len(rendered_sha256) == 2


def test_species_full_chain_prompt_assets_render_primary_and_targeted_modes() -> None:
    prompt_root = Path(__file__).resolve().parents[3] / "prompts/xray/nacos/primary"
    declared_variables = PromptVariablesContract(
        required=["SAFE_STUDY_CONTEXT_JSON", "OUTPUT_SCHEMA_JSON"],
        optional=["PRIMARY_RESULT_JSON"],
    ).model_dump(mode="json")
    message_contract = {
        "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
        "user_context_keys": [
            "SAFE_STUDY_CONTEXT_JSON",
            "PRIMARY_RESULT_JSON",
        ],
    }
    rendered_sha256: set[str] = set()

    for species in ("cat", "dog"):
        content = (
            prompt_root
            / species
            / "zh-CN"
            / f"ms-image.x-ray.primary.{species}.zh-CN.v4.0.0.md"
        ).read_text()
        normalized, inferred_variables = normalize_imported_prompt(content)
        variables = PromptImportService._resolve_variables(
            inferred_variables=inferred_variables,
            declared_variables=declared_variables,
        )
        assert set(inferred_variables["required"]) == {
            "SAFE_STUDY_CONTEXT_JSON",
            "OUTPUT_SCHEMA_JSON",
            "PRIMARY_RESULT_JSON",
        }
        validate_prompt_message_template(
            content=normalized,
            message_contract_json=message_contract,
        )

        primary = PromptRenderer.render(
            content=normalized,
            variables_json=variables,
            safe_variables={
                "SAFE_STUDY_CONTEXT_JSON": {
                    "prompt_mode": "primary",
                    "species": species,
                },
                "OUTPUT_SCHEMA_JSON": {"type": "object"},
            },
            max_prompt_chars=120_000,
        )
        targeted = PromptRenderer.render(
            content=normalized,
            variables_json=variables,
            safe_variables={
                "SAFE_STUDY_CONTEXT_JSON": {
                    "prompt_mode": "targeted",
                    "species": species,
                    "selected_family_key": "thoracic",
                    "selected_focus_key": "pulmonary_pattern",
                },
                "OUTPUT_SCHEMA_JSON": {"type": "object"},
                "PRIMARY_RESULT_JSON": {"summary": "待复核结果"},
            },
            max_prompt_chars=120_000,
        )

        assert "联合主读完整结果——仅作为待复核输入" not in primary.rendered_text
        assert "联合主读完整结果——仅作为待复核输入" in targeted.rendered_text
        assert "待复核结果" in targeted.rendered_text
        assert "PRIMARY_RESULT_JSON" not in targeted.rendered_text
        rendered_sha256.update(
            {primary.rendered_prompt_sha256, targeted.rendered_prompt_sha256}
        )

    assert len(rendered_sha256) == 4


def test_prompt_import_explicit_variables_only_change_required_optional_split() -> None:
    inferred = {
        "contract_version": "prompt-variables.v1",
        "required": [
            "OUTPUT_SCHEMA_JSON",
            "PRIMARY_RESULT_JSON",
            "SAFE_STUDY_CONTEXT_JSON",
        ],
        "optional": [],
    }
    declared = {
        "contract_version": "prompt-variables.v1",
        "required": ["SAFE_STUDY_CONTEXT_JSON", "OUTPUT_SCHEMA_JSON"],
        "optional": ["PRIMARY_RESULT_JSON"],
    }

    assert PromptImportService._resolve_variables(
        inferred_variables=inferred,
        declared_variables=declared,
    ) == declared
    with pytest.raises(
        AIControlValidationError, match="prompt_import_variables_mismatch"
    ):
        PromptImportService._resolve_variables(
            inferred_variables=inferred,
            declared_variables={
                **declared,
                "optional": [],
            },
        )

    payload = PromptImportRequest(
        request_id="request_1",
        prompt_key="xray_cat_primary",
        version="4.0.0",
        name="Cat XRay full-chain Prompt",
        service_code="ms-image",
        module_code="xray",
        variant="cat",
        variables_json=declared,
        message_contract_json={
            "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
            "user_context_keys": [
                "SAFE_STUDY_CONTEXT_JSON",
                "PRIMARY_RESULT_JSON",
            ],
        },
    )
    assert payload.variables_json is not None
    assert payload.variables_json.optional == ["PRIMARY_RESULT_JSON"]


def test_prompt_source_preserves_ms_ai_fast_template_semantics() -> None:
    content = (
        "请只输出符合 Schema 的结果。\n"
        "上下文：{{ SAFE_STUDY_CONTEXT_JSON }}\n"
        "Schema：{{ OUTPUT_SCHEMA_JSON }}\n"
        "Primary：{{ PRIMARY_RESULT_JSON }}\n"
    )
    normalized, variables = normalize_imported_prompt(content)
    assert normalized == content
    assert variables["contract_version"] == "prompt-variables.v1"
    assert "SAFE_STUDY_CONTEXT_JSON" in variables["required"]
    assert "OUTPUT_SCHEMA_JSON" in variables["required"]
    assert "PRIMARY_RESULT_JSON" in variables["required"]
    assert variables["optional"] == []

    dollar_content = (
        "请只输出符合 Schema 的结果。\n"
        "上下文：$SAFE_STUDY_CONTEXT_JSON\n"
        "Schema：$OUTPUT_SCHEMA_JSON\n"
    )
    dollar_normalized, dollar_variables = normalize_imported_prompt(dollar_content)
    assert dollar_normalized == dollar_content
    assert "SAFE_STUDY_CONTEXT_JSON" in dollar_variables["required"]
    assert "OUTPUT_SCHEMA_JSON" in dollar_variables["required"]

    business_dollar, business_variables = normalize_imported_prompt(
        "请参考 $base_info 与 $previous_answer。"
    )
    assert business_dollar == "请参考 $base_info 与 $previous_answer。"
    assert business_variables["required"] == ["base_info", "previous_answer"]
    assert business_variables["optional"] == []

    supported_templates = [
        "{% if x %}yes{% endif %}",
        "{{ SAFE_STUDY_CONTEXT_JSON | tojson }}",
        "{{ func(x) }}",
        "{{ obj.attr }}",
        "$unknown_variable",
        "{{ ARBITRARY_VARIABLE }}",
    ]
    for supported in supported_templates:
        normalized_supported, supported_variables = normalize_imported_prompt(supported)
        assert normalized_supported == supported
        assert supported_variables["required"]

    with pytest.raises(PromptSourceUnsafeError, match="prompt_source_template_invalid"):
        normalize_imported_prompt("{{ SAFE_STUDY_CONTEXT_JSON }")


def test_prompt_source_receipt_sha_binds_namespace_and_content() -> None:
    namespace = "c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9"
    receipt = build_source_receipt(
        source_type="nacos",
        namespace=namespace,
        source_key="ms.ai-pic.xray-primary.default.zh-CN",
        release_or_version="v1",
        requested_variant="default",
        resolved_variant="default",
        fallback_used=False,
        content_sha256="a" * 64,
    )
    assert receipt["contract_version"] == "prompt-source-receipt.v1"
    assert receipt["namespace"] == namespace
    assert receipt_sha256(receipt) == receipt_sha256(dict(receipt))
    assert receipt_sha256(receipt) != receipt_sha256(
        {**receipt, "namespace": "another-namespace"}
    )
    assert receipt_sha256(receipt) != receipt_sha256(
        {**receipt, "content_sha256": "b" * 64}
    )


def test_runtime_gate_requires_ms_ai_fast_platform_configuration(monkeypatch) -> None:
    from apps.backend.core.config import settings

    monkeypatch.setattr(
        settings, "AI_PLATFORM_OPENAI_BASE_URL", "https://platform.example/v1"
    )
    monkeypatch.setattr(settings, "AI_PLATFORM_API_KEY", "provider-key")
    monkeypatch.setattr(settings, "PROJECT_ENV", "production")
    assert AIRequestService._runtime_gate_allows() is True
    monkeypatch.setattr(settings, "AI_PLATFORM_API_KEY", "")
    assert AIRequestService._runtime_gate_allows() is False


def test_default_environment_file_and_template_match_ms_ai_fast_platform_contract() -> (
    None
):
    assert Settings.Config.env_file == ".env"

    env_example = (Path(__file__).resolve().parents[3] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "AI_PLATFORM_OPENAI_BASE_URL=" in env_example
    assert "AI_PLATFORM_API_KEY=" in env_example
    assert "AI_PLATFORM_TIMEOUT_SECONDS=120" in env_example
    assert "GEMINI_API_KEYS=" not in env_example
    assert "AI_GATEWAY_" not in env_example


def test_prompt_nacos_settings_accept_ms_ai_fast_environment_contract(
    monkeypatch,
) -> None:
    values = {
        "NACOS_SERVER_ADDR": "https://nacos.example",
        "NACOS_CONTEXT_PATH": "/shared-nacos",
        "NACOS_USERNAME": "shared-user",
        "NACOS_PASSWORD": "shared-password",
        "NACOS_PROMPT_NAMESPACE_ID": "shared-prompt-namespace",
        "NACOS_PROMPT_TIMEOUT_SECONDS": "11",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    configured = Settings(_env_file=None, ALGORITHM="HS256")

    assert configured.NACOS_SERVER_ADDR == "https://nacos.example"
    assert configured.NACOS_CONTEXT_PATH == "/shared-nacos"
    assert configured.NACOS_USERNAME == "shared-user"
    assert configured.NACOS_PASSWORD == "shared-password"
    assert configured.NACOS_PROMPT_NAMESPACE_ID == "shared-prompt-namespace"
    assert configured.NACOS_PROMPT_TIMEOUT_SECONDS == 11


def test_prompt_nacos_namespace_is_distinct_from_general_nacos_namespace(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NACOS_NAMESPACE_ID", "shared-namespace")
    monkeypatch.setenv("NACOS_PROMPT_NAMESPACE_ID", "prompt-namespace")

    configured = Settings(_env_file=None, ALGORITHM="HS256")

    assert configured.NACOS_NAMESPACE_ID == "shared-namespace"
    assert configured.NACOS_PROMPT_NAMESPACE_ID == "prompt-namespace"


def test_message_contract_context_key_must_be_declared_in_control_plane() -> None:
    variables = {
        "contract_version": "prompt-variables.v1",
        "required": ["OUTPUT_SCHEMA_JSON"],
        "optional": [],
    }
    message_contract = {
        "contract_version": "prompt-message-contract.v1",
        "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
    }
    with pytest.raises(
        AIControlValidationError,
        match="prompt_message_contract_context_variable_missing",
    ):
        PromptTemplateService._validate_message_contract_variables(
            variables_json=variables,
            message_contract_json=message_contract,
        )


def test_config_compiler_rejects_message_contract_with_undeclared_context_key() -> None:
    content = "只输出符合 Schema 的结果：{{ OUTPUT_SCHEMA_JSON }}"
    prompt = SimpleNamespace(
        language="zh-CN",
        status="validated",
        content=content,
        variables_json={
            "contract_version": "prompt-variables.v1",
            "required": ["OUTPUT_SCHEMA_JSON"],
            "optional": [],
        },
        content_sha256=sha256_text(content),
        message_contract_json={
            "contract_version": "prompt-message-contract.v1",
            "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
        },
        source_receipt_json=None,
        source_receipt_sha256=None,
    )
    with pytest.raises(
        AIControlValidationError,
        match="config_prompt_message_contract_variable_missing",
    ):
        AIConfigCompiler._validate_prompt(
            prompt=prompt,
            require_validated=False,
        )


def _targeted_v2_facts(*, include_selection: bool = True) -> tuple[Any, Any]:
    task = SimpleNamespace(
        id="task_1",
        request_snapshot_json={
            "snapshot_contract_version": TASK_REQUEST_SNAPSHOT_V2,
            "species": "dog",
            "series": [],
        },
    )
    stage_input = {
        "study_revision_id": "revision_1",
        "previous_output": {
            "complete_medical_result": {
                "medical_status": "review_required",
                "findings": [],
            }
        },
        "selected_strategy_key": "focused_recheck",
        "source_finding_ids": ["finding_1"],
        "coverage_proof": {"complete_study": True},
        "route_reason_codes": ["primary_residual_failure"],
    }
    if include_selection:
        stage_input.update(
            selected_family_key="thoracic",
            selected_focus_key="cardiac_silhouette",
        )
    return task, SimpleNamespace(input_json=stage_input)


def test_targeted_v2_command_preserves_unique_route_evidence() -> None:
    task, stage = _targeted_v2_facts()

    command = build_targeted_ai_request_command(task=task, stage=stage)

    assert command.applicable_family_keys == ()
    assert command.family_key == "thoracic"
    assert command.focus_key == "cardiac_silhouette"
    assert command.strategy_key == "focused_recheck"
    assert command.safe_context["selected_family_key"] == "thoracic"
    assert command.safe_context["selected_focus_key"] == "cardiac_silhouette"
    assert (
        command.safe_context["primary_complete_result"]
        is command.primary_complete_result
    )

    captured: dict[str, Any] = {}

    class CapturingCompiler:
        def compile_targeted(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(prompt_kind="targeted")

    compiled = command.compile(CapturingCompiler())

    assert compiled.prompt_kind == "targeted"
    assert captured["family_key"] == "thoracic"
    assert captured["focus_key"] == "cardiac_silhouette"
    assert captured["strategy_key"] == "focused_recheck"
    assert captured["primary_complete_result"] == command.primary_complete_result


def test_targeted_v2_command_rejects_missing_route_selection() -> None:
    task, stage = _targeted_v2_facts(include_selection=False)

    with pytest.raises(
        PromptContractError,
        match="targeted_prompt_selection_missing",
    ):
        build_targeted_ai_request_command(task=task, stage=stage)


def test_v2_runtime_uses_renderer_and_does_not_import_mutable_source_dals() -> None:
    runtime_path = (
        Path(__file__).resolve().parents[1]
        / "services/runtime/service/ai_request_service.py"
    )
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert {"AIAPIConnectionDal", "AIPromptTemplateDal", "AIModelPoolDal"}.isdisjoint(
        imported_names
    )

    source = runtime_path.read_text(encoding="utf-8")
    assert "def _prepare_v2_provider_disabled_call" in source
    assert "PromptRenderer" in source
    assert "PromptMessageAssembler" in source
    assert '"provider_disabled"' in source


def test_targeted_profile_requires_primary_result_message_context() -> None:
    with pytest.raises(
        AIControlValidationError,
        match="config_targeted_prompt_message_contract_required",
    ):
        AIConfigCompiler._validate_profile_prompt_contract(
            profile_key="xray_targeted_review_v1",
            variables_json=VALID_VARIABLES,
            message_contract=None,
        )

    with pytest.raises(
        AIControlValidationError,
        match="config_targeted_prompt_primary_result_context_required",
    ):
        AIConfigCompiler._validate_profile_prompt_contract(
            profile_key="xray_targeted_review_v1",
            variables_json=VALID_VARIABLES,
            message_contract={
                "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
                "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
            },
        )

    AIConfigCompiler._validate_profile_prompt_contract(
        profile_key="xray_targeted_review_v1",
        variables_json=VALID_VARIABLES,
        message_contract={
            "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
            "user_context_keys": [
                "SAFE_STUDY_CONTEXT_JSON",
                "PRIMARY_RESULT_JSON",
            ],
        },
    )

    with pytest.raises(
        AIControlValidationError,
        match="config_targeted_prompt_message_contract_required",
    ):
        AIConfigCompiler._validate_profile_prompt_contract(
            profile_key="xray_targeted_review_v2",
            variables_json=VALID_VARIABLES,
            message_contract=None,
        )


def test_config_compiler_selects_versioned_complete_result_schema_by_profile() -> None:
    v1 = AIConfigCompiler._output_schema(profile_key="xray_primary_v1")
    v2 = AIConfigCompiler._output_schema(profile_key="xray_primary_v2")

    assert v1["x-ms-image-contract-version"] == "complete-medical-result.v1"
    assert v2["x-ms-image-contract-version"] == "complete-medical-result.v2"
    assert v2["properties"]["result_schema_version"]["const"] == (
        "xray-complete-medical-result.v2"
    )
    assert sha256_json(v1) != sha256_json(v2)


def test_targeted_v2_profile_remains_experiment_scoped() -> None:
    base = {
        "request_id": "request_1",
        "config_key": "xray_diagnose",
        "version": "v2",
        "name": "XRay Targeted v2",
        "modality_type": "xray",
        "task_type": "diagnose",
        "profile_key": "xray_targeted_review_v2",
        "scope_key": "global",
        "prompt_template_id": "prompt_1",
        "model_pool_id": "pool_1",
        "budget_policy_json": {
            "contract_version": "ai-budget-policy.v1",
            "max_prompt_chars": 10_000,
            "max_input_images": 10,
            "max_total_calls": 2,
            "max_total_attempts": 2,
            "task_deadline_ms": 120_000,
            "reserve_before_send": True,
        },
    }

    with pytest.raises(
        ValidationError,
        match="targeted_profile_experiment_scope_required",
    ):
        AIConfigCreate(**base)


def test_frozen_targeted_config_revalidates_primary_result_message_context() -> None:
    connection_capability = {
        "contract_version": "connection-capability.v1",
        "supports_images": True,
        "supports_json_schema": True,
        "supports_idempotency_key": True,
        "supports_request_lookup": True,
        "max_input_images": 10,
        "max_context_tokens": 32_768,
        "declared_regions": [],
        "gateway_profile": normalize_gateway_profile(None),
    }
    connection_metadata = {
        "connection_key": "xray_provider",
        "version": "v1",
        "provider_type": "openai_compatible",
        "api_format": "responses",
        "base_url": "https://provider.example/v1",
        "region": None,
        "capability_json": connection_capability,
    }
    connection_sha = canonical_connection_metadata_sha256(connection_metadata)
    connection = SimpleNamespace(
        id="connection_v1",
        status="validated",
        connection_sha256=connection_sha,
        **connection_metadata,
    )
    lane = {
        **VALID_LANE,
        "connection_sha256": connection_sha,
    }
    lane_plan = {
        "contract_version": "ai-model-pool-lanes.v1",
        "lanes": [lane],
    }
    pool = SimpleNamespace(
        id="pool_v1",
        status="validated",
        pool_key="xray_primary",
        version="v1",
        execution_mode="single",
        winner_policy="single",
        lane_count=1,
        lane_plan_json=lane_plan,
        pool_sha256=sha256_json(
            {
                "pool_key": "xray_primary",
                "version": "v1",
                "execution_mode": "single",
                "winner_policy": "single",
                "lane_count": 1,
                "lane_plan_json": lane_plan,
            }
        ),
    )
    prompt_content = "输出完整病例级 XRay 结构化结果。"
    prompt = SimpleNamespace(
        id="prompt_v1",
        prompt_key="xray_complete",
        version="v1",
        language="zh-CN",
        status="validated",
        content=prompt_content,
        variables_json=VALID_VARIABLES,
        message_contract_json={
            "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
            "user_context_keys": [
                "SAFE_STUDY_CONTEXT_JSON",
                "PRIMARY_RESULT_JSON",
            ],
        },
        content_sha256=sha256_text(prompt_content),
        source_receipt_json=None,
        source_receipt_sha256=None,
    )
    compiler = AIConfigCompiler(build_default_registry())
    compiled = compiler.compile(
        source={
            "config_key": "xray_targeted",
            "version": "v1",
            "name": "XRay Targeted",
            "modality_type": "xray",
            "task_type": "diagnostic_analysis",
            "profile_key": "xray_targeted_review_v1",
            "activation_scope": "global",
            "scope_key": "global",
            "prompt_template_id": prompt.id,
            "model_pool_id": pool.id,
            "budget_policy_json": {
                "contract_version": "ai-budget-policy.v1",
                "max_prompt_chars": 10_000,
                "max_input_images": 10,
                "max_total_calls": 2,
                "max_total_attempts": 2,
                "task_deadline_ms": 120_000,
                "reserve_before_send": True,
            },
        },
        prompt=prompt,
        pool=pool,
        connections=[connection],
        require_validated_sources=True,
    )
    frozen_lane = compiled.values["model_snapshot_json"]["lanes"][0]
    assert "secret_ref" not in frozen_lane
    assert not any(
        marker in key.casefold()
        for key in frozen_lane
        for marker in ("secret", "authorization", "password", "api_key", "credential")
    )
    frozen = SimpleNamespace(**compiled.values)
    frozen.prompt_message_contract_json = {
        "contract_version": PROMPT_MESSAGE_CONTRACT_V1,
        "user_context_keys": ["SAFE_STUDY_CONTEXT_JSON"],
    }

    with pytest.raises(
        AIControlValidationError,
        match="config_targeted_prompt_primary_result_context_required",
    ):
        compiler.verify_frozen_integrity(frozen)


def test_xray_prompt_commands_expose_stable_prompt_mode() -> None:
    task, targeted_stage = _targeted_v2_facts()
    primary_stage = SimpleNamespace(input_json={"study_revision_id": "revision_1"})

    primary = build_primary_ai_request_command(task=task, stage=primary_stage)
    targeted = build_targeted_ai_request_command(task=task, stage=targeted_stage)

    assert primary.safe_context["prompt_mode"] == "primary"
    assert primary.safe_context["species"] == "dog"
    assert primary.safe_context["clinical_context_allowlist"] == {}
    assert targeted.safe_context["prompt_mode"] == "targeted"
    assert targeted.safe_context["species"] == "dog"
    assert targeted.safe_context["clinical_context_allowlist"] == {}


def test_xray_prompt_commands_consume_only_frozen_clinical_context() -> None:
    from apps.backend.core.ai.clinical_context import freeze_clinical_context

    task, targeted_stage = _targeted_v2_facts()
    frozen = freeze_clinical_context(
        {
            "contract_version": "xray-clinical-context.v1",
            "source": {
                "system": "ms-ai-fast",
                "recorded_at": "2026-08-28T02:30:00Z",
                "temporal_scope": "available_at_request",
            },
            "chief_complaint": "间歇性咳嗽三天",
            "study_reason": "评估胸部影像",
        }
    )
    task.request_snapshot_json.update(frozen.snapshot_fields())
    primary_stage = SimpleNamespace(input_json={"study_revision_id": "revision_1"})

    primary = build_primary_ai_request_command(task=task, stage=primary_stage)
    targeted = build_targeted_ai_request_command(task=task, stage=targeted_stage)

    assert primary.safe_context["clinical_context_allowlist"] == frozen.payload
    assert targeted.safe_context["clinical_context_allowlist"] == frozen.payload


def test_xray_prompt_commands_fail_closed_on_clinical_context_hash_drift() -> None:
    from apps.backend.core.ai.clinical_context import freeze_clinical_context

    task, targeted_stage = _targeted_v2_facts()
    frozen = freeze_clinical_context(
        {
            "contract_version": "xray-clinical-context.v1",
            "source": {
                "system": "ms-ai-fast",
                "recorded_at": "2026-08-28T02:30:00Z",
                "temporal_scope": "available_at_request",
            },
            "chief_complaint": "间歇性咳嗽三天",
        }
    )
    task.request_snapshot_json.update(frozen.snapshot_fields())
    task.request_snapshot_json["clinical_context_sha256"] = "0" * 64
    primary_stage = SimpleNamespace(input_json={"study_revision_id": "revision_1"})

    with pytest.raises(
        PromptContractError,
        match="task_clinical_context_snapshot_mismatch",
    ):
        build_primary_ai_request_command(task=task, stage=primary_stage)
    with pytest.raises(
        PromptContractError,
        match="task_clinical_context_snapshot_mismatch",
    ):
        build_targeted_ai_request_command(task=task, stage=targeted_stage)


def test_legacy_prompt_leakage_allowlist_accepts_existing_prompt_mode() -> None:
    from apps.backend.core.ai.prompting.leakage import validate_primary_context

    task, _ = _targeted_v2_facts()
    primary_stage = SimpleNamespace(input_json={"study_revision_id": "revision_1"})
    context = build_primary_ai_request_command(
        task=task,
        stage=primary_stage,
    ).safe_context
    context = {
        key: value
        for key, value in context.items()
        if key != "technical_evidence_available"
    }

    validate_primary_context(context)


def test_xray_prompt_commands_reject_missing_species_in_v2_snapshot() -> None:
    task, targeted_stage = _targeted_v2_facts()
    task.request_snapshot_json = {
        **task.request_snapshot_json,
        "species": None,
    }
    primary_stage = SimpleNamespace(input_json={"study_revision_id": "revision_1"})

    with pytest.raises(PromptContractError, match="xray_species_snapshot_invalid"):
        build_primary_ai_request_command(task=task, stage=primary_stage)
    with pytest.raises(PromptContractError, match="xray_species_snapshot_invalid"):
        build_targeted_ai_request_command(task=task, stage=targeted_stage)


def test_xray_runtime_config_requires_exact_five_image_budget() -> None:
    capability = {
        "supports_images": True,
        "supports_json_schema": True,
        "max_input_images": 5,
        "max_context_tokens": 8192,
    }
    lane = {
        **VALID_LANE,
        "generation_params": {
            **VALID_LANE["generation_params"],
            "max_output_tokens": 1024,
        },
    }
    budget = {
        "contract_version": "ai-budget-policy.v1",
        "max_prompt_chars": 10000,
        "max_input_images": 4,
        "max_total_calls": 1,
        "max_total_attempts": 1,
        "task_deadline_ms": 120000,
        "reserve_before_send": True,
    }

    with pytest.raises(
        AIControlValidationError,
        match="config_xray_image_budget_invalid",
    ):
        AIConfigCompiler._validate_budget(
            budget_policy=budget,
            prompt_content="prompt",
            lane=lane,
            capability=capability,
            required_logical_calls=1,
            xray_image_contract_required=True,
        )

    budget["max_input_images"] = 5
    AIConfigCompiler._validate_budget(
        budget_policy=budget,
        prompt_content="prompt",
        lane=lane,
        capability=capability,
        required_logical_calls=1,
        xray_image_contract_required=True,
    )

    capability["max_input_images"] = 4
    with pytest.raises(
        AIControlValidationError,
        match="config_xray_connection_image_capability_invalid",
    ):
        AIConfigCompiler._validate_budget(
            budget_policy=budget,
            prompt_content="prompt",
            lane=lane,
            capability=capability,
            required_logical_calls=1,
            xray_image_contract_required=True,
        )
