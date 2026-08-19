from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.imaging_common import normalize_required_text


class AIConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    modality_type: str = Field(min_length=1, max_length=32)
    task_type: str = Field(min_length=1, max_length=48)
    profile_key: str = Field(default="zero_model_replay_v1", min_length=1, max_length=64)
    capability_manifest: dict[str, Any] = Field(default_factory=lambda: {"provider_disabled": True})
    provider_plan: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    budget_policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config_key", "version", "modality_type", "task_type", "profile_key")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


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


__all__ = ["AIConfigActivateRequest", "AIConfigCreate", "AIConfigResponse"]
