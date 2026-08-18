from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator


class LegacySessionStartRequest(BaseModel):
    """Legacy session-start input mapped onto the ms-image Session fact."""

    model_config = ConfigDict(extra="forbid")

    pet_profile_id: str | int
    module_type: int = Field(default=3)
    content: str | list[str] | None = None
    request_id: str | None = Field(default=None, min_length=1, max_length=128)


class LegacySessionStartResponse(BaseModel):
    session_id: str
    medical_record_id: str
    pet_profile_id: str
    session_status: str


class LegacyPreparationImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: str | None = Field(default=None, min_length=1, max_length=4096)
    source_image_ref: str | None = Field(default=None, min_length=1, max_length=512)
    body_part: str | None = Field(default=None, max_length=64)
    study_event_key: str | None = Field(default=None, max_length=128)
    study_date: str | None = Field(default=None, max_length=32)
    study_time: str | None = Field(default=None, max_length=32)
    view_code: str | None = Field(default=None, max_length=64)
    source_image_index: NonNegativeInt | None = None
    mime_type: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_one_source(self):
        if not self.image_url and not self.source_image_ref:
            raise ValueError("legacy_image_source_required")
        return self


class LegacyPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    image_urls: list[LegacyPreparationImage] = Field(min_length=1, max_length=50)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    study_id: str | None = Field(default=None, min_length=1, max_length=128)
    species: str | None = Field(default=None, max_length=32)
    body_scope: str | None = Field(default=None, max_length=64)


class LegacyPreparationResult(BaseModel):
    source_index: int
    source_image_ref: str
    asset_id: str
    status: str


class LegacyPreparationResponse(BaseModel):
    session_id: str
    study_id: str
    study_revision_id: str
    status: str
    total: int
    input_total: int
    unique_image_total: int
    duplicate_input_count: int
    success_count: int
    failed_count: int
    preparation_task_id: str
    results: list[LegacyPreparationResult]


class LegacyReportSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    image_urls: list[LegacyPreparationImage] = Field(default_factory=list, max_length=50)
    xray_list: list[str | int] = Field(default_factory=list, max_length=256)
    force_refresh_preparation: bool = False
    force_refresh_segmentation: bool = False
    include_segmentation_preview: bool = True
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    study_revision_id: str | None = Field(default=None, min_length=1, max_length=128)
    species: str | None = Field(default=None, max_length=32)
    body_scope: str | None = Field(default=None, max_length=64)


class LegacyReportTaskResponse(BaseModel):
    job_id: str
    task_id: str
    run_id: str
    session_id: str
    study_revision_id: str
    status: str
    report_type: str = "xray_v2"
    reused: bool = False
    medical_status: str = "not_produced"


class LegacyTaskStatusResponse(BaseModel):
    task_id: str
    run_id: str
    session_id: str
    status: str
    execution_status: str
    medical_status: str
    publish_status: str
    consumer_status: str


class LegacyReportViewResponse(BaseModel):
    session_id: str
    status: str
    run_id: str | None = None
    task_id: str | None = None
    study_id: str | None = None
    study_revision_id: str | None = None
    decision: str | None = None
    primary_diagnosis: str | None = None
    review_required: bool | None = None
    final_reason: str | None = None
    disease_list: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "LegacyPreparationImage",
    "LegacyPreparationRequest",
    "LegacyPreparationResponse",
    "LegacyReportSubmitRequest",
    "LegacyReportTaskResponse",
    "LegacyReportViewResponse",
    "LegacySessionStartRequest",
    "LegacySessionStartResponse",
    "LegacyTaskStatusResponse",
]
