from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.imaging_common import normalize_required_text


class EvaluationArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_ref: dict[str, Any]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: dict[str, Any]


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
    error_code: str | None = None
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
    status: str
    state_version: int
    summary_json: dict[str, Any] | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=64)

    @field_validator("job_id")
    @classmethod
    def normalize_job_id(cls, value: str) -> str:
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
    "EvaluationArtifactInput",
    "EvaluationArtifactResponse",
    "EvaluationJobCreate",
    "EvaluationJobResponse",
    "EvaluationRunResponse",
    "EvaluationRunCreate",
]
