"""Strict request/response contracts for the AI Prompt control plane.

The JSON contracts in this module are deliberately narrow: every persisted JSON
column has a version marker and forbids arbitrary provider or template fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.core.ai.prompting.renderer import PromptRenderError, PromptRenderer
from apps.backend.schemas.imaging_common import normalize_required_text

T = TypeVar("T")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PromptVariablesContract(_StrictModel):
    contract_version: str = "prompt-variables.v1"
    required: list[str] = Field(default_factory=list, max_length=16)
    optional: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_names(self) -> "PromptVariablesContract":
        try:
            PromptRenderer.declared_variables(self.model_dump(mode="python"))
        except PromptRenderError as exc:
            raise ValueError(str(exc)) from exc
        return self


class GatewayProfileContract(_StrictModel):
    """Frozen OpenAI-compatible Gateway qualification contract."""

    contract_version: str = "ai-gateway-profile.v1"
    adapter_key: str = "openai-compatible"
    provider_enabled: bool = False
    qualification_status: str = "disabled"
    streaming_mode: str = "json"
    image_url_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    allowed_actual_models: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("allowed_actual_models")
    @classmethod
    def normalize_allowed_models(cls, value: list[str]) -> list[str]:
        normalized = [normalize_required_text(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("gateway_profile_actual_models_duplicate")
        return sorted(normalized)

    @model_validator(mode="after")
    def verify_contract(self) -> "GatewayProfileContract":
        if (
            self.contract_version != "ai-gateway-profile.v1"
            or self.adapter_key != "openai-compatible"
            or self.qualification_status not in {"disabled", "qualified"}
            or self.streaming_mode not in {"json", "aggregate_sse"}
        ):
            raise ValueError("gateway_profile_invalid")
        if self.provider_enabled and self.qualification_status != "qualified":
            raise ValueError("gateway_profile_qualification_required")
        if self.provider_enabled and not self.allowed_actual_models:
            raise ValueError("gateway_profile_actual_models_required")
        if not self.provider_enabled and self.qualification_status != "disabled":
            raise ValueError("gateway_profile_disabled_state_invalid")
        return self


class PromptMessageContract(_StrictModel):
    """Optional multi-message runtime contract for a complete Prompt body."""

    contract_version: str = "prompt-message-contract.v1"
    user_context_keys: list[str] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def verify_contract(self) -> "PromptMessageContract":
        allowed = {"SAFE_STUDY_CONTEXT_JSON", "PRIMARY_RESULT_JSON"}
        if (
            self.contract_version != "prompt-message-contract.v1"
            or len(self.user_context_keys) != len(set(self.user_context_keys))
            or any(key not in allowed for key in self.user_context_keys)
            or "SAFE_STUDY_CONTEXT_JSON" not in self.user_context_keys
        ):
            raise ValueError("prompt_message_contract_invalid")
        return self


class ConnectionCapabilityContract(_StrictModel):
    contract_version: str = "connection-capability.v1"
    supports_images: bool
    supports_json_schema: bool
    supports_idempotency_key: bool
    supports_request_lookup: bool
    max_input_images: int = Field(ge=1, le=100)
    max_context_tokens: int = Field(ge=1, le=1_000_000)
    declared_regions: list[str] = Field(default_factory=list, max_length=32)
    gateway_profile: GatewayProfileContract = Field(default_factory=GatewayProfileContract)

    @field_validator("declared_regions")
    @classmethod
    def normalize_regions(cls, value: list[str]) -> list[str]:
        normalized = [normalize_required_text(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("connection_regions_duplicate")
        return normalized

    @model_validator(mode="after")
    def verify_version(self) -> "ConnectionCapabilityContract":
        if self.contract_version != "connection-capability.v1":
            raise ValueError("connection_capability_contract_version_invalid")
        return self


class GenerationParams(_StrictModel):
    temperature: float = Field(ge=0.0, le=2.0)
    top_p: float = Field(gt=0.0, le=1.0)
    max_output_tokens: int = Field(ge=1, le=32_768)


class ModelPoolLane(_StrictModel):
    lane_key: str = Field(min_length=1, max_length=64)
    priority: int = Field(ge=1, le=2)
    connection_id: str = Field(min_length=1, max_length=64)
    connection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_model: str = Field(min_length=1, max_length=128)
    timeout_ms: int = Field(ge=1_000, le=120_000)
    max_attempts: int = Field(ge=1, le=1)
    generation_params: GenerationParams

    @field_validator("lane_key", "connection_id", "requested_model")
    @classmethod
    def normalize_lane_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ModelPoolLanePlanContract(_StrictModel):
    contract_version: str = "ai-model-pool-lanes.v1"
    lanes: list[ModelPoolLane] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def verify_single_lane_contract(self) -> "ModelPoolLanePlanContract":
        if self.contract_version != "ai-model-pool-lanes.v1":
            raise ValueError("model_pool_lane_contract_version_invalid")
        lanes = self.lanes
        if len(lanes) != 1 or lanes[0].lane_key != "primary" or lanes[0].priority != 1:
            raise ValueError("model_pool_single_primary_lane_required")
        return self


class BudgetPolicyContract(_StrictModel):
    contract_version: str = "ai-budget-policy.v1"
    max_prompt_chars: int = Field(ge=1, le=120_000)
    max_input_images: int = Field(ge=1, le=100)
    max_total_calls: int = Field(ge=1, le=32)
    max_total_attempts: int = Field(ge=1, le=32)
    task_deadline_ms: int = Field(ge=1_000, le=600_000)
    reserve_before_send: bool

    @model_validator(mode="after")
    def verify_budget_contract(self) -> "BudgetPolicyContract":
        if self.contract_version != "ai-budget-policy.v1":
            raise ValueError("ai_budget_policy_contract_version_invalid")
        if self.max_total_attempts < self.max_total_calls:
            raise ValueError("ai_budget_attempts_less_than_calls")
        if self.reserve_before_send is not True:
            raise ValueError("ai_budget_reserve_before_send_required")
        return self


class CommandRequest(_StrictModel):
    request_id: str = Field(min_length=1, max_length=128)

    @field_validator("request_id")
    @classmethod
    def normalize_request_id(cls, value: str) -> str:
        return normalize_required_text(value)


class StateCommandRequest(CommandRequest):
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)


class RetireCommandRequest(StateCommandRequest):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return normalize_required_text(value)


class PromptCreate(CommandRequest):
    prompt_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    language: str = Field(default="zh-CN", min_length=1, max_length=16)
    content: str = Field(min_length=1, max_length=120_000)
    variables_json: PromptVariablesContract
    message_contract_json: PromptMessageContract | None = None

    @field_validator("prompt_key", "version", "name", "language")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("language")
    @classmethod
    def require_supported_language(cls, value: str) -> str:
        if value != "zh-CN":
            raise ValueError("ai_prompt_template_language_invalid")
        return value


class PromptUpdate(StateCommandRequest):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    language: str = Field(default="zh-CN", min_length=1, max_length=16)
    content: str = Field(min_length=1, max_length=120_000)
    variables_json: PromptVariablesContract
    message_contract_json: PromptMessageContract | None = None

    @field_validator("name", "language")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("language")
    @classmethod
    def require_supported_language(cls, value: str) -> str:
        if value != "zh-CN":
            raise ValueError("ai_prompt_template_language_invalid")
        return value


class PromptSummaryResponse(_StrictModel):
    id: str
    prompt_key: str
    version: str
    name: str
    description: str | None = None
    language: str
    content_sha256: str
    message_contract_json: PromptMessageContract | None = None
    source_receipt_sha256: str | None = None
    status: str
    state_version: int
    validated_at: datetime | None = None
    retired_at: datetime | None = None
    created_by_id: str
    updated_by_id: str
    created_at: datetime
    updated_at: datetime


class PromptDetailResponse(PromptSummaryResponse):
    content: str
    variables_json: PromptVariablesContract


class PromptImportRequest(CommandRequest):
    """Import a published external Prompt into the control plane."""

    prompt_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    service_code: str = Field(min_length=1, max_length=64)
    module_code: str = Field(min_length=1, max_length=64)
    variant: str = Field(default="default", min_length=1, max_length=64)
    locale: str = Field(default="zh-CN", min_length=1, max_length=16)
    nacos_release_or_version: str | None = Field(default=None, max_length=64)
    nacos_label: str | None = Field(default=None, max_length=64)
    namespace_id: str | None = Field(default=None, min_length=1, max_length=128)
    message_contract_json: PromptMessageContract | None = None

    @field_validator(
        "prompt_key",
        "version",
        "name",
        "service_code",
        "module_code",
        "variant",
        "locale",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("description", "nacos_release_or_version", "nacos_label", "namespace_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else None

    @field_validator("locale")
    @classmethod
    def require_supported_language(cls, value: str) -> str:
        if value != "zh-CN":
            raise ValueError("ai_prompt_template_language_invalid")
        return value


class PromptImportResponse(PromptDetailResponse):
    """Prompt detail plus the frozen external-source import facts."""

    nacos_data_id: str
    requested_variant: str
    resolved_variant: str
    fallback_used: bool


class ConnectionCreate(CommandRequest):
    connection_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    provider_type: str = Field(min_length=1, max_length=64)
    api_format: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=500)
    secret_ref: str = Field(min_length=1, max_length=500)
    region: str | None = Field(default=None, max_length=64)
    capability_json: ConnectionCapabilityContract

    @field_validator("connection_key", "version", "name", "provider_type", "api_format", "base_url", "secret_ref")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ConnectionUpdate(StateCommandRequest):
    name: str = Field(min_length=1, max_length=160)
    provider_type: str = Field(min_length=1, max_length=64)
    api_format: str = Field(min_length=1, max_length=64)
    base_url: str = Field(min_length=1, max_length=500)
    secret_ref: str = Field(min_length=1, max_length=500)
    region: str | None = Field(default=None, max_length=64)
    capability_json: ConnectionCapabilityContract

    @field_validator("name", "provider_type", "api_format", "base_url", "secret_ref")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ConnectionResponse(_StrictModel):
    id: str
    connection_key: str
    version: str
    name: str
    provider_type: str
    api_format: str
    base_url: str
    region: str | None = None
    capability_json: ConnectionCapabilityContract
    connection_sha256: str
    secret_ref_type: str
    secret_ref_fingerprint: str
    status: str
    state_version: int
    validated_at: datetime | None = None
    retired_at: datetime | None = None
    created_by_id: str
    updated_by_id: str
    created_at: datetime
    updated_at: datetime


class ModelPoolCreate(CommandRequest):
    pool_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    execution_mode: str = Field(default="single", min_length=1, max_length=32)
    winner_policy: str = Field(default="single", min_length=1, max_length=64)
    lane_count: int = Field(default=1, ge=1, le=1)
    lane_plan_json: ModelPoolLanePlanContract

    @field_validator("pool_key", "version", "name", "execution_mode", "winner_policy")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ModelPoolUpdate(StateCommandRequest):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    execution_mode: str = Field(default="single", min_length=1, max_length=32)
    winner_policy: str = Field(default="single", min_length=1, max_length=64)
    lane_count: int = Field(default=1, ge=1, le=1)
    lane_plan_json: ModelPoolLanePlanContract

    @field_validator("name", "execution_mode", "winner_policy")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ModelPoolResponse(_StrictModel):
    id: str
    pool_key: str
    version: str
    name: str
    description: str | None = None
    execution_mode: str
    winner_policy: str
    lane_count: int
    lane_plan_json: ModelPoolLanePlanContract
    pool_sha256: str
    status: str
    state_version: int
    validated_at: datetime | None = None
    retired_at: datetime | None = None
    created_by_id: str
    updated_by_id: str
    created_at: datetime
    updated_at: datetime


class ControlAuditResponse(_StrictModel):
    id: str
    resource_type: str
    resource_id: str
    resource_key: str
    action_type: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    changed_fields_json: dict[str, Any]
    reason: str | None = None
    request_id: str
    actor_type: str
    actor_id: str
    result_type: str
    error_code: str | None = None
    created_at: datetime


class PageResult(_StrictModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    limit: int


__all__ = [
    "BudgetPolicyContract",
    "CommandRequest",
    "ConnectionCapabilityContract",
    "ConnectionCreate",
    "ConnectionResponse",
    "ConnectionUpdate",
    "ControlAuditResponse",
    "GatewayProfileContract",
    "GenerationParams",
    "ModelPoolCreate",
    "ModelPoolLane",
    "ModelPoolLanePlanContract",
    "ModelPoolResponse",
    "ModelPoolUpdate",
    "PageResult",
    "PromptCreate",
    "PromptDetailResponse",
    "PromptImportRequest",
    "PromptImportResponse",
    "PromptMessageContract",
    "PromptSummaryResponse",
    "PromptUpdate",
    "PromptVariablesContract",
    "RetireCommandRequest",
    "StateCommandRequest",
]
