from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.imaging_common import normalize_required_text


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_id: str = Field(min_length=1, max_length=64)
    study_revision_id: str = Field(min_length=1, max_length=64)
    request_id: str = Field(min_length=1, max_length=128)
    task_type: str = Field(default="replay", min_length=1, max_length=48)
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("study_id", "study_revision_id", "request_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in {"replay", "diagnose"}:
            raise ValueError("task_type_not_supported")
        return normalized


class TaskCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    requester_id: str
    request_id: str
    task_type: str
    business_key: str
    ai_config_id: str
    compiled_pipeline_sha256: str
    study_revision_id: str
    run_mode: str
    execution_status: str
    ai_medical_status: str
    state_version: int
    request_snapshot_json: dict[str, Any] | None = None
    request_sha256: str
    trace_id: str
    error_code: str | None = None
    cancel_requested_by_id: str | None = None
    cancel_reason: str | None = None
    cancel_requested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StageCheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    stage_no: int
    stage_key: str
    handler_key: str
    handler_version: str
    status: str
    state_version: int
    lease_generation: int
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


__all__ = ["StageCheckpointResponse", "TaskCancelRequest", "TaskCreate", "TaskResponse"]
