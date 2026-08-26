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
    validate_secret_ref_structure,
)
from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    normalize_gateway_profile,
)
from apps.backend.core.ai.prompting.message_contract import (
    PROMPT_MESSAGE_CONTRACT_V1,
    PromptMessageAssembler,
)
from apps.backend.core.ai.prompting import PromptContractError
from apps.backend.core.ai.prompting.contracts import sha256_json, sha256_text
from apps.backend.core.ai.prompting.renderer import PromptRenderError, PromptRenderer
from apps.backend.core.pipeline import build_default_registry
from apps.backend.core.config import Settings
from apps.backend.schemas.ai_config import AIConfigResponse
from apps.backend.schemas.ai_control import (
    BudgetPolicyContract,
    ConnectionResponse,
    GatewayProfileContract,
    GenerationParams,
    ModelPoolLanePlanContract,
    PromptVariablesContract,
)
from apps.backend.services.ai_control.service.ai_config_service import AIConfigService
from apps.backend.services.ai_control.service.config_compiler import AIConfigCompiler
from apps.backend.services.ai_control.service.errors import AIControlValidationError
from apps.backend.services.ai_control.service.prompt_template_service import (
    PromptTemplateService,
)
from apps.backend.services.ai_control.service.prompt_source import (
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


def _connection_metadata(*, base_url: str) -> dict[str, Any]:
    return {
        "connection_key": "xray_provider",
        "version": "v1",
        "provider_type": "openai_compatible",
        "api_format": "responses",
        "base_url": base_url,
        "secret_ref": "secret-manager://ai/xray/provider",
        "region": "provider-region",
        "capability_json": {
            "contract_version": "connection-capability.v1",
            "supports_images": True,
        },
    }


def _assert_no_sensitive_keys(value: Any) -> None:
    forbidden = ("secret", "token", "authorization", "password", "api_key", "credential")
    if isinstance(value, dict):
        assert not any(marker in key.casefold() for key in value for marker in forbidden)
        for nested in value.values():
            _assert_no_sensitive_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_sensitive_keys(nested)


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


@pytest.mark.parametrize(
    "secret_ref",
    [
        "secret-manager://ai/xray\nAuthorization: Bearer unsafe",
        "secret-manager://ai/xray\runsafe",
        "Authorization: secret-manager://ai/xray",
        "bearer opaque-value",
    ],
)
def test_secret_reference_rejects_header_or_newline_shapes(secret_ref: str) -> None:
    with pytest.raises(ConnectionContractError, match="ai_connection_secret_ref_invalid"):
        validate_secret_ref_structure(secret_ref)


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
    assert '{{' not in first.rendered_text
    assert first.rendered_prompt_sha256 == PromptRenderer.render(
        content=content,
        variables_json=VALID_VARIABLES,
        safe_variables={
            "SAFE_STUDY_CONTEXT_JSON": {"study_id": "study_1", "views": ["VD", "LL"]},
            "OUTPUT_SCHEMA_JSON": {"required": ["result"], "type": "object"},
            "PRIMARY_RESULT_JSON": {"summary": "stable"},
        },
        max_prompt_chars=10_000,
    ).rendered_prompt_sha256


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
    content = (
        "检查上下文：$SAFE_STUDY_CONTEXT_JSON，Schema：$OUTPUT_SCHEMA_JSON"
    )
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


def test_renderer_supports_declared_business_dollar_variable_and_rejects_undeclared() -> None:
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
        "输出示例：{\"recg\": {\"photo\": \"皮肤图\"}}\n"
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
    assert legacy_activation_slot(**common) == "xray.primary:global:global:xray:analysis"


def test_control_plane_json_contracts_accept_prompt_variables_and_reject_unsupported_lanes() -> None:
    variables = PromptVariablesContract(required=["base_info", "ARBITRARY"])
    assert variables.required == ["base_info", "ARBITRARY"]

    with pytest.raises(ValidationError, match="prompt_variables_contract_invalid"):
        PromptVariablesContract(required=["invalid-name"])

    with pytest.raises(ValidationError, match="model_pool_single_primary_lane_required"):
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


def test_control_plane_responses_do_not_expose_raw_snapshots_or_secret_references() -> None:
    assert "secret_ref" not in ConnectionResponse.model_fields
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
    with pytest.raises(GatewayContractError, match="gateway_profile_qualification_required"):
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
    assert qualified["allowed_actual_models"] == ["provider-model-a", "provider-model-b"]
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
    with pytest.raises(
        ValidationError, match="gateway_profile_actual_models_required"
    ):
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
    assert without_context.messages_json == [
        {"role": "user", "content": "角色与边界"}
    ]


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

    monkeypatch.setattr(settings, "AI_PLATFORM_OPENAI_BASE_URL", "https://platform.example/v1")
    monkeypatch.setattr(settings, "AI_PLATFORM_API_KEY", "provider-key")
    monkeypatch.setattr(settings, "PROJECT_ENV", "production")
    assert AIRequestService._runtime_gate_allows() is True
    monkeypatch.setattr(settings, "AI_PLATFORM_API_KEY", "")
    assert AIRequestService._runtime_gate_allows() is False


def test_default_environment_file_and_template_match_ms_ai_fast_platform_contract() -> None:
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
            "species": "canine",
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
    assert command.safe_context["primary_complete_result"] is command.primary_complete_result

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
        "secret_ref": "secret-manager://ai/xray/provider",
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
    primary_stage = SimpleNamespace(
        input_json={"study_revision_id": "revision_1"}
    )

    primary = build_primary_ai_request_command(task=task, stage=primary_stage)
    targeted = build_targeted_ai_request_command(task=task, stage=targeted_stage)

    assert primary.safe_context["prompt_mode"] == "primary"
    assert targeted.safe_context["prompt_mode"] == "targeted"
