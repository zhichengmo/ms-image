from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.imaging_common import normalize_required_text


class EvaluationControlHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy"]
    service: Literal["evaluation_control"]
    timestamp: datetime


class EvaluationControlReadinessComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool
    ready: bool
    state: str = Field(min_length=1, max_length=32)
    error: str | None = Field(default=None, max_length=80)


class EvaluationControlReadinessComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_database: EvaluationControlReadinessComponent
    schema_revision: EvaluationControlReadinessComponent
    control_plane_jwt: EvaluationControlReadinessComponent


class EvaluationControlReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    readiness_scope: Literal["evaluation_control"]
    components: EvaluationControlReadinessComponents


class EvaluationArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_ref: dict[str, Any]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: dict[str, Any]

    @field_validator("object_ref")
    @classmethod
    def validate_object_ref(cls, value: dict[str, Any]) -> dict[str, Any]:
        required = {
            "storage_profile",
            "object_key",
            "sha256",
            "size_bytes",
            "content_type",
        }
        allowed = required | {"object_version_id", "kms_key_version"}
        if set(value) - allowed or not required.issubset(value):
            raise ValueError("evaluation_object_ref_fields_invalid")
        object_key = str(value["object_key"])
        if (
            not str(value["storage_profile"]).strip()
            or not object_key
            or "://" in object_key
            or object_key.startswith("/")
            or ".." in object_key.split("/")
        ):
            raise ValueError("evaluation_object_ref_identity_invalid")
        if value["content_type"] != "application/json":
            raise ValueError("evaluation_object_ref_content_type_invalid")
        if (
            not isinstance(value["size_bytes"], int)
            or not 0 < value["size_bytes"] <= 64 * 1024 * 1024
        ):
            raise ValueError("evaluation_object_ref_size_invalid")
        if not isinstance(value["sha256"], str) or len(value["sha256"]) != 64:
            raise ValueError("evaluation_object_ref_sha_invalid")
        return value


class EvaluationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scorer_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_split: dict[str, Any]
    denominator_contract: dict[str, Any]
    input_manifest: EvaluationArtifactInput
    sanitization: EvaluationArtifactInput

    @field_validator("request_id")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        return normalize_required_text(value)


class EvaluationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    requester_id: str
    business_key: str
    request_payload_sha256: str
    dataset_fingerprint: str
    gold_fingerprint: str
    scorer_fingerprint: str
    experiment_fingerprint: str
    case_split_json: dict[str, Any]
    denominator_contract_json: dict[str, Any]
    input_manifest_artifact_id: str
    sanitization_artifact_id: str
    status: str
    state_version: int
    lease_owner_id: str | None = None
    lease_generation: int = 0
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    retry_count: int = 0
    next_retry_at: datetime | None = None
    result_artifact_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    run_no: int
    dataset_fingerprint: str
    gold_fingerprint: str
    scorer_fingerprint: str
    experiment_fingerprint: str
    case_split_sha256: str
    denominator_contract_sha256: str
    input_manifest_artifact_sha256: str
    sanitization_artifact_sha256: str
    status: str
    state_version: int
    summary_json: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=64)

    @field_validator("job_id")
    @classmethod
    def normalize_job_id(cls, value: str) -> str:
        return normalize_required_text(value)


class EvaluationJobStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class ExecuteEvaluationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("job_id", "trace_id")
    @classmethod
    def normalize_message_text(cls, value: str) -> str:
        return normalize_required_text(value)


class EvaluationArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    run_id: str | None = None
    artifact_kind: str
    object_ref_json: dict[str, Any]
    content_sha256: str
    provenance_json: dict[str, Any]
    visibility: str
    status: str
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "EvaluationControlHealthResponse",
    "EvaluationControlReadinessComponent",
    "EvaluationControlReadinessComponents",
    "EvaluationControlReadinessResponse",
    "EvaluationArtifactInput",
    "EvaluationArtifactResponse",
    "EvaluationJobCreate",
    "EvaluationJobResponse",
    "EvaluationJobStateRequest",
    "EvaluationRunResponse",
    "EvaluationRunCreate",
    "ExecuteEvaluationMessage",
]
