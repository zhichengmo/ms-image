from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.core.ai.prompting.contracts import PRIMARY_FAMILY_ORDER
from apps.backend.schemas.imaging_common import normalize_required_text


class AIConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    modality_type: str = Field(min_length=1, max_length=32)
    task_type: str = Field(min_length=1, max_length=48)
    profile_key: str = Field(
        default="zero_model_replay_v1", min_length=1, max_length=64
    )
    activation_scope: str = Field(default="global", min_length=1, max_length=32)
    scope_key: str = Field(default="global", min_length=1, max_length=128)
    prompt_catalog_revision: str = Field(
        default="zh-CN.2026-08-20.1", min_length=1, max_length=128
    )
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    schema_catalog_revision: str = Field(
        default="complete_medical_result.v1", min_length=1, max_length=128
    )
    model_policy: dict[str, Any] = Field(default_factory=dict)
    capability_manifest: dict[str, Any] = Field(
        default_factory=lambda: {"provider_disabled": True}
    )
    provider_plan: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    budget_policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "config_key",
        "version",
        "modality_type",
        "task_type",
        "profile_key",
        "activation_scope",
        "scope_key",
        "prompt_catalog_revision",
        "schema_catalog_revision",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @model_validator(mode="after")
    def validate_scope_and_policy(self):
        if self.activation_scope not in {"global", "experiment"}:
            raise ValueError("ai_config_activation_scope_invalid")
        if self.activation_scope == "global" and self.scope_key != "global":
            raise ValueError("ai_config_global_scope_key_invalid")
        if self.activation_scope == "experiment" and self.scope_key == "global":
            raise ValueError("ai_config_experiment_scope_key_invalid")
        if self.profile_key == "xray_targeted_review_v1":
            if self.activation_scope != "experiment":
                raise ValueError("targeted_profile_experiment_scope_required")
            targeted = self.prompt_policy.get("targeted")
            if not isinstance(targeted, dict) or targeted.get("enabled") is not True:
                raise ValueError("targeted_prompt_policy_required")
        if self.profile_key == "xray_primary_v1":
            targeted = self.prompt_policy.get("targeted")
            if isinstance(targeted, dict) and targeted.get("enabled") is True:
                raise ValueError("primary_prompt_policy_targeted_forbidden")
        families = self.prompt_policy.get("primary_family_keys")
        if families is not None and (
            not isinstance(families, list)
            or any(item not in PRIMARY_FAMILY_ORDER for item in families)
        ):
            raise ValueError("prompt_policy_primary_family_invalid")
        return self


class AIConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    config_key: str
    version: str
    activation_scope: str
    scope_key: str
    activation_slot: str | None = None
    modality_type: str
    task_type: str
    capability_manifest_json: dict[str, Any]
    compiled_pipeline_sha256: str
    stage_registry_contract_version: str
    provider_plan_json: dict[str, Any]
    budget_policy_json: dict[str, Any]
    prompt_catalog_revision: str
    prompt_bundle_sha256: str
    schema_catalog_revision: str
    schema_bundle_sha256: str
    model_policy_json: dict[str, Any]
    release_fingerprint: str
    config_sha256: str
    status: str
    state_version: int
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class AIConfigActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class AIConfigStateRequest(AIConfigActivateRequest):
    pass


__all__ = [
    "AIConfigActivateRequest",
    "AIConfigCreate",
    "AIConfigResponse",
    "AIConfigStateRequest",
]
