from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.core.ai.clinical_context import (
    CLINICAL_CONTEXT_MAX_SOURCE_SYSTEM_CHARS,
    CLINICAL_CONTEXT_MAX_TEXT_CHARS,
    CLINICAL_CONTEXT_TEMPORAL_SCOPE,
    CLINICAL_CONTEXT_V1,
    normalize_clinical_context_payload,
)
from apps.backend.schemas.anatomy_localization import (
    AnatomyLocalizationTaskSummaryResponse,
)
from apps.backend.schemas.imaging_common import (
    normalize_required_text,
    normalize_utc_datetime,
)


TASK_EXECUTION_STATUSES = frozenset(
    {
        "pending",
        "queued",
        "running",
        "retry_wait",
        "completed",
        "failed",
        "cancelled",
        "dead_letter",
    }
)
TASK_TYPES = frozenset(
    {
        "replay",
        "diagnose",
        "anatomy_localization",
        "xray_quality_control",
        "xray_study_screening",
        "xray_system_analysis",
    }
)


class TaskClinicalContextSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str = Field(
        min_length=1,
        max_length=CLINICAL_CONTEXT_MAX_SOURCE_SYSTEM_CHARS,
    )
    recorded_at: datetime
    temporal_scope: Literal["available_at_request"] = CLINICAL_CONTEXT_TEMPORAL_SCOPE

    @field_validator("system")
    @classmethod
    def normalize_system(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("recorded_at")
    @classmethod
    def normalize_recorded_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value).replace(tzinfo=timezone.utc)


class TaskClinicalContext(BaseModel):
    """Caller-declared facts available before this diagnostic request."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["xray-clinical-context.v1"] = CLINICAL_CONTEXT_V1
    source: TaskClinicalContextSource
    chief_complaint: str | None = Field(
        default=None,
        max_length=CLINICAL_CONTEXT_MAX_TEXT_CHARS,
    )
    study_reason: str | None = Field(
        default=None,
        max_length=CLINICAL_CONTEXT_MAX_TEXT_CHARS,
    )

    @field_validator("chief_complaint", "study_reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @model_validator(mode="after")
    def validate_contract(self) -> "TaskClinicalContext":
        normalize_clinical_context_payload(self.model_dump(mode="json"))
        return self


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    study_id: str = Field(min_length=1, max_length=64)
    study_revision_id: str = Field(min_length=1, max_length=64)
    request_id: str = Field(min_length=1, max_length=128)
    task_type: str = Field(default="replay", min_length=1, max_length=48)
    species: str | None = Field(default=None, max_length=16)
    quality_review_task_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    source_task_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    pet_profile_id: str | None = Field(default=None, min_length=1, max_length=64)
    clinical_context: TaskClinicalContext | None = None
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("study_id", "study_revision_id", "request_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("quality_review_task_id", "source_task_id")
    @classmethod
    def normalize_optional_task_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @field_validator("pet_profile_id")
    @classmethod
    def normalize_optional_pet_profile_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in TASK_TYPES:
            raise ValueError("task_type_not_supported")
        return normalized

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_required_text(value).lower()
        if normalized not in {"cat", "dog"}:
            raise ValueError("task_species_not_supported")
        return normalized

    @model_validator(mode="after")
    def validate_task_context(self) -> "TaskCreate":
        if self.task_type == "diagnose" and self.species is None:
            raise ValueError("task_species_required_for_diagnose")
        if self.task_type == "anatomy_localization" and self.species is None:
            raise ValueError("task_species_required_for_anatomy_localization")
        if self.task_type == "xray_quality_control" and self.species is None:
            raise ValueError("task_species_required_for_xray_quality_control")
        if self.task_type == "xray_study_screening" and self.species is None:
            raise ValueError("task_species_required_for_xray_study_screening")
        if self.task_type == "xray_system_analysis" and self.species is None:
            raise ValueError("task_species_required_for_xray_system_analysis")
        if self.task_type != "diagnose" and self.clinical_context is not None:
            raise ValueError("task_clinical_context_diagnose_only")
        if self.task_type != "diagnose" and self.pet_profile_id is not None:
            raise ValueError("task_pet_profile_diagnose_only")
        if (
            self.task_type
            not in {"diagnose", "xray_study_screening", "xray_system_analysis"}
            and self.quality_review_task_id is not None
        ):
            raise ValueError("task_quality_review_reference_diagnose_only")
        if (
            self.task_type != "anatomy_localization"
            and self.source_task_id is not None
        ):
            raise ValueError("task_source_reference_anatomy_localization_only")
        if (
            self.task_type == "anatomy_localization"
            and self.source_task_id is None
        ):
            raise ValueError("task_source_reference_required_for_anatomy_localization")
        return self


class TaskCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class TaskPageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    study_id: str | None = Field(default=None, min_length=1, max_length=64)
    execution_status: str | None = Field(default=None, min_length=1, max_length=32)
    task_type: str | None = Field(default=None, min_length=1, max_length=48)
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("session_id", "study_id")
    @classmethod
    def normalize_scope_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @field_validator("execution_status")
    @classmethod
    def validate_execution_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_required_text(value).lower()
        if normalized not in TASK_EXECUTION_STATUSES:
            raise ValueError("task_execution_status_invalid")
        return normalized

    @field_validator("task_type")
    @classmethod
    def validate_page_task_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_required_text(value).lower()
        if normalized not in TASK_TYPES:
            raise ValueError("task_type_not_supported")
        return normalized

    @field_validator("created_from", "created_to")
    @classmethod
    def normalize_created_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_utc_datetime(value)

    @model_validator(mode="after")
    def validate_page_scope(self) -> "TaskPageQuery":
        if self.session_id is None and self.study_id is None:
            raise ValueError("task_page_scope_required")
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("task_created_range_invalid")
        return self


class TaskStatusResponse(BaseModel):
    """Runtime-safe Task summary without frozen execution snapshots."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    source_task_id: str | None = None
    request_id: str
    task_type: str
    study_revision_id: str
    run_mode: str
    execution_status: str
    ai_medical_status: str
    state_version: int
    current_report_id: str | None = None
    trace_id: str
    error_code: str | None = None
    next_retry_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[TaskStatusResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    source_task_id: str | None = None
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
    current_report_id: str | None = None
    anatomy_localization: AnatomyLocalizationTaskSummaryResponse | None = None
    request_snapshot_json: dict[str, Any] | None = None
    request_sha256: str
    trace_id: str
    error_code: str | None = None
    next_retry_at: datetime | None = None
    cancel_requested_by_id: str | None = None
    cancel_reason: str | None = None
    cancel_requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
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


__all__ = [
    "StageCheckpointResponse",
    "TaskCancelRequest",
    "TaskClinicalContext",
    "TaskClinicalContextSource",
    "TaskCreate",
    "TaskPageQuery",
    "TaskPageResult",
    "TaskResponse",
    "TaskStatusResponse",
]
