"""Public API contracts for immutable ``ai-config.v2`` records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.core.ai.config_contract import AI_CONFIG_V2
from apps.backend.core.pipeline import XRAY_TARGETED_REVIEW_PROFILE_V2
from apps.backend.schemas.ai_control import (
    BudgetPolicyContract,
    CommandRequest,
    StateCommandRequest,
)
from apps.backend.schemas.imaging_common import normalize_required_text


class _StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AIConfigCreate(CommandRequest):
    """The only writable Config input: source IDs plus stable business scope."""

    config_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    modality_type: str = Field(min_length=1, max_length=32)
    task_type: str = Field(min_length=1, max_length=48)
    profile_key: str = Field(min_length=1, max_length=64)
    activation_scope: str = Field(default="global", min_length=1, max_length=32)
    scope_key: str = Field(default="global", min_length=1, max_length=128)
    prompt_template_id: str = Field(min_length=1, max_length=64)
    model_pool_id: str = Field(min_length=1, max_length=64)
    budget_policy_json: BudgetPolicyContract

    @field_validator(
        "config_key",
        "version",
        "name",
        "modality_type",
        "task_type",
        "profile_key",
        "activation_scope",
        "scope_key",
        "prompt_template_id",
        "model_pool_id",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @model_validator(mode="after")
    def validate_scope(self) -> "AIConfigCreate":
        if self.activation_scope not in {"global", "experiment"}:
            raise ValueError("ai_config_activation_scope_invalid")
        if self.activation_scope == "global" and self.scope_key != "global":
            raise ValueError("ai_config_global_scope_key_invalid")
        if self.activation_scope == "experiment" and self.scope_key == "global":
            raise ValueError("ai_config_experiment_scope_key_invalid")
        if (
            self.profile_key
            in {
                "xray_targeted_review_v1",
                XRAY_TARGETED_REVIEW_PROFILE_V2,
            }
            and self.activation_scope != "experiment"
        ):
            raise ValueError("targeted_profile_experiment_scope_required")
        return self


class AIConfigCompilePreview(_StrictConfigModel):
    """Non-sensitive compile result; never serializes content or secret_ref."""

    config_contract_version: str = AI_CONFIG_V2
    config_key: str
    version: str
    profile_key: str
    prompt_template_id: str
    prompt_key: str
    prompt_version: str
    prompt_content_sha256: str
    model_pool_id: str
    model_pool_key: str
    model_pool_version: str
    model_snapshot_sha256: str
    output_schema_sha256: str
    compiled_pipeline_sha256: str
    stage_registry_contract_version: str
    capability_manifest_sha256: str
    budget_policy_sha256: str
    config_sha256: str
    release_fingerprint: str


class AIConfigResponse(_StrictConfigModel):
    """Safe Config metadata. Frozen content/model snapshots are internal only."""

    id: str
    config_key: str
    version: str
    name: str | None = None
    config_contract_version: str | None = None
    modality_type: str
    task_type: str
    profile_key: str | None = None
    activation_scope: str
    scope_key: str
    activation_slot: str | None = None
    prompt_template_id: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    prompt_content_sha256: str | None = None
    prompt_message_contract_json: dict[str, Any] | None = None
    prompt_source_receipt_sha256: str | None = None
    model_pool_id: str | None = None
    model_pool_key: str | None = None
    model_pool_version: str | None = None
    model_snapshot_sha256: str | None = None
    output_schema_sha256: str | None = None
    gateway_profile_json: dict[str, Any] | None = None
    capability_manifest_json: dict[str, Any]
    compiled_pipeline_sha256: str
    stage_registry_contract_version: str
    budget_policy_json: dict[str, Any]
    release_fingerprint: str
    config_sha256: str
    status: str
    state_version: int
    error_code: str | None = None
    validated_at: datetime | None = None
    activated_at: datetime | None = None
    retired_at: datetime | None = None
    created_by_id: str | None = None
    updated_by_id: str | None = None
    created_at: datetime
    updated_at: datetime

    # Read-only v1 compatibility summaries.  They intentionally omit raw
    # bundle content and any potential Secret reference.
    prompt_catalog_revision: str | None = None
    prompt_bundle_sha256: str | None = None
    schema_catalog_revision: str | None = None
    schema_bundle_sha256: str | None = None
    model_policy_json: dict[str, Any] | None = None
    provider_plan_json: dict[str, Any] | None = None


class AIConfigStateRequest(StateCommandRequest):
    pass


class AIConfigActivateRequest(AIConfigStateRequest):
    expected_current_active_id: str | None = Field(
        default=None, min_length=1, max_length=64
    )
    expected_current_active_state_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("expected_current_active_id", "reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else None

    @model_validator(mode="after")
    def validate_active_expectation(self) -> "AIConfigActivateRequest":
        has_id = self.expected_current_active_id is not None
        has_version = self.expected_current_active_state_version is not None
        if has_id != has_version:
            raise ValueError("ai_config_current_active_expectation_pair_required")
        return self


class AIConfigRollbackRequest(CommandRequest):
    target_config_id: str = Field(min_length=1, max_length=64)
    expected_target_state_version: int = Field(ge=0)
    expected_current_active_id: str = Field(min_length=1, max_length=64)
    expected_current_active_state_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("target_config_id", "expected_current_active_id", "reason")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


__all__ = [
    "AIConfigActivateRequest",
    "AIConfigCompilePreview",
    "AIConfigCreate",
    "AIConfigResponse",
    "AIConfigRollbackRequest",
    "AIConfigStateRequest",
]
