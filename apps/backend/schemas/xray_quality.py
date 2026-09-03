"""Runtime API schemas for X-Ray batch image quality review."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.image import ImageProjectionProvenance
from apps.backend.schemas.imaging_common import normalize_required_text


class XRayQualityReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str = Field(min_length=1, max_length=64)
    study_revision_id: str = Field(min_length=1, max_length=64)
    request_id: str = Field(min_length=1, max_length=128)
    species: Literal["cat", "dog"]
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("study_id", "study_revision_id", "request_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class XRayImageQualityObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    sequence_no: int = Field(ge=1, le=5)
    is_valid_xray: bool
    species_consistency: Literal["consistent", "inconsistent", "indeterminate"]
    primary_body_part: Literal[
        "head_neck",
        "thorax",
        "abdomen",
        "axial_skeleton",
        "appendicular_skeleton",
        "other",
        "indeterminate",
    ]
    visible_body_parts: list[
        Literal[
            "head_neck",
            "thorax",
            "abdomen",
            "axial_skeleton",
            "appendicular_skeleton",
            "other",
            "indeterminate",
        ]
    ]
    observed_projection: Literal[
        "right_lateral",
        "left_lateral",
        "lateral_indeterminate",
        "ventrodorsal",
        "dorsoventral",
        "craniocaudal",
        "caudocranial",
        "mediolateral",
        "lateromedial",
        "oblique",
        "open_mouth",
        "other",
        "indeterminate",
    ]
    projection_consistency: Literal["consistent", "inconsistent", "indeterminate"]
    quality_status: Literal["diagnostic", "limited", "non_diagnostic"]
    quality_issue_codes: list[
        Literal[
            "positioning",
            "rotation",
            "anatomy_cutoff",
            "underexposure",
            "overexposure",
            "low_contrast",
            "motion",
            "artifact",
            "marker_missing",
            "projection_indeterminate",
            "non_xray_or_unsupported",
        ]
    ]


class XRayImageQualityResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["xray-image-quality.v1"]
    species: Literal["cat", "dog"]
    result_status: Literal["complete", "partial", "unavailable"]
    images: list[XRayImageQualityObservationResponse] = Field(
        min_length=2,
        max_length=5,
    )


class XRayQualityImageResponse(XRayImageQualityObservationResponse):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    declared_projection: str
    projection_provenance: ImageProjectionProvenance
    series_manifest_sha256: str


class XRayQualityResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["xray-image-quality.v1"]
    species: Literal["cat", "dog"]
    result_status: Literal["complete", "partial", "unavailable"]
    images: list[XRayQualityImageResponse] = Field(min_length=2, max_length=5)


class XRayQualityReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    study_id: str
    study_revision_id: str
    stage_checkpoint_id: str
    source_call_id: str
    output_sha256: str
    result: XRayQualityResultResponse


__all__ = [
    "XRayImageQualityObservationResponse",
    "XRayImageQualityResultResponse",
    "XRayQualityImageResponse",
    "XRayQualityResultResponse",
    "XRayQualityReviewCreate",
    "XRayQualityReviewResponse",
]
