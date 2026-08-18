from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, field_validator

from .image_contract import normalize_source_mime_type


class XRayImageRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_index: NonNegativeInt = Field(description="请求内稳定图像序号")
    source_image_ref: str = Field(min_length=1, max_length=512, description="短期内部图像引用")
    mime_type: str | None = Field(default=None, max_length=128, description="允许的媒体 MIME")

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str | None) -> str | None:
        return normalize_source_mime_type(value)


class XRayRunCreate(BaseModel):
    """Validation-only request; tenant and subject come from the verified JWT."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128, description="幂等请求标识")
    session_id: str | None = Field(default=None, max_length=64, description="所属 Session opaque 标识")
    study_id: str | None = Field(default=None, max_length=128, description="所属 Study opaque 标识")
    case_request_id: str | None = Field(default=None, max_length=128, description="病例请求 opaque 标识")
    requested_operation: str = Field(default="diagnose", min_length=1, max_length=32)
    contract_version: str = Field(default="xray-run.v1", min_length=1, max_length=64)
    study_revision: str = Field(min_length=1, max_length=128, description="Study 版本标识")
    expected_manifest: list[XRayImageRef] = Field(min_length=1, max_length=256)
    safe_metadata: dict[str, Any] | None = Field(default=None, description="脱敏安全元数据")
    validation_only: Literal[True] = Field(default=True, description="Phase 1 只能 validation-only")


class XRayRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    session_id: str | None = None
    study_id: str | None = None
    requested_operation: str
    request_id: str
    contract_version: str
    release_fingerprint: str
    execution_status: str
    ai_medical_status: str
    delivery_status: str
    engineering_eligibility: str
    state_version: int
    validation_only: bool
    trace_ref: str


class XRayRunQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = Field(default=None, min_length=1, max_length=64)
    page: int = Field(default=1, ge=1, le=100000)
    limit: int = Field(default=20, ge=1, le=100)


class XRayCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=64)
    expected_version: int = Field(ge=0)


class XRayExecutionRequest(BaseModel):
    """Request a validation-only worker execution for one committed Run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=64)


class XRayTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    run_id: str
    stage_key: str
    event_type: str
    state_version: int
    late_flag: str
    fingerprint: str | None = None


class XRayCheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checkpoint_id: str
    run_id: str
    stage_key: str
    attempt_id: str
    status: str
    expected_version: int
    input_hash: str | None = None
    output_hash: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_class: str | None = None
    late_flag: str


class XRayCoverageEvidenceResponse(BaseModel):
    """Safe four-set lineage view; refs are opaque asset IDs only."""

    model_config = ConfigDict(extra="forbid")

    expected_source_image_refs: list[str] = Field(default_factory=list)
    resolved_source_image_refs: list[str] = Field(default_factory=list)
    requested_source_image_refs: list[str] = Field(default_factory=list)
    sent_source_image_refs: list[str] = Field(default_factory=list)
    expected_image_sha256: list[str] = Field(default_factory=list)
    resolved_image_sha256: list[str] = Field(default_factory=list)
    requested_image_sha256: list[str] = Field(default_factory=list)
    sent_image_sha256: list[str] = Field(default_factory=list)
    coverage_status: str = "unknown"
    image_ordered_sha256: str | None = None


class XRayModelCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_call_id: str
    run_id: str
    node_key: str
    attempt_id: str
    module_key: str | None = None
    provider_key: str
    requested_model: str | None = None
    actual_model: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    prompt_sha256: str | None = None
    rendered_sha256: str | None = None
    schema_key: str | None = None
    schema_sha256: str | None = None
    requested_language: str | None = None
    actual_language: str | None = None
    image_ordered_sha256: str | None = None
    coverage_evidence: XRayCoverageEvidenceResponse | None = None
    raw_output_sha256: str | None = None
    parsed_output_sha256: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    retry_index: int
    fallback_used: str
    error_class: str | None = None
    created_at: datetime | None = None


class XRayOutboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    run_id: str
    task_id: str
    stage_key: str
    event_type: str
    publish_status: str
    consumer_status: str
    consumer_attempt_count: int = 0
    consumer_next_retry_at: datetime | None = None
    consumer_finished_at: datetime | None = None
    consumer_last_error: str | None = None
    attempt_count: int
    next_retry_at: datetime | None = None
    published_at: datetime | None = None
    last_error: str | None = None


class XRayExecutionResponse(BaseModel):
    """Safe, tenant-scoped technical execution view; no raw prompt/output."""

    run: XRayRunResponse
    input_tokens: int = Field(default=0, ge=0, description="Run 累计输入 token 数")
    output_tokens: int = Field(default=0, ge=0, description="Run 累计输出 token 数")
    total_tokens: int = Field(default=0, ge=0, description="Run 累计 token 总数")
    checkpoints: list[XRayCheckpointResponse]
    model_calls: list[XRayModelCallResponse]
    traces: list[XRayTraceResponse]
    outbox: list[XRayOutboxResponse]
