"""Owner-safe Runtime responses for Anatomy Localization v1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnatomyLocalizationPrepareViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    image_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=5,
    )

    @field_validator("task_id")
    @classmethod
    def normalize_task_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("task_id_required")
        return normalized

    @field_validator("image_ids")
    @classmethod
    def normalize_image_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value]
        if any(not item or len(item) > 64 for item in normalized):
            raise ValueError("image_id_invalid")
        if len(normalized) != len(set(normalized)):
            raise ValueError("image_id_duplicate")
        return normalized


class AnatomyLocalizationViewImageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    series_id: str
    sequence_no: int = Field(ge=1, le=5)
    projection: str
    file_format: str
    content_type: str
    pixel_width: int | None = Field(default=None, ge=1)
    pixel_height: int | None = Field(default=None, ge=1)
    expires_at: datetime
    signed_url: str = Field(repr=False)


class AnatomyLocalizationPrepareViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    study_id: str
    study_revision_id: str
    expires_in: int = Field(ge=1, le=900)
    images: list[AnatomyLocalizationViewImageResponse] = Field(
        min_length=1,
        max_length=5,
    )


class AnatomyLocalizationLegendLabelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    display_name: str
    sort_order: int = Field(ge=1)


class AnatomyLocalizationLegendSystemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str
    display_name: str
    color: str = Field(pattern=r"^#[0-9A-F]{6}$")
    sort_order: int = Field(ge=1)
    labels: list[AnatomyLocalizationLegendLabelResponse] = Field(min_length=1)


class AnatomyLocalizationLegendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_contract_version: Literal["xray-anatomy-labels.v1"]
    locale: Literal["zh-CN"]
    systems: list[AnatomyLocalizationLegendSystemResponse] = Field(
        min_length=6,
        max_length=6,
    )


class AnatomyLocalizationOrganResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str
    label: str
    bbox: tuple[float, float, float, float]


class AnatomyLocalizationImageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    series_id: str
    sequence_no: int = Field(ge=1, le=5)
    projection: str
    series_manifest_sha256: str
    status: Literal["localized", "not_localized"]
    reason_code: Literal[
        "no_supported_anatomy_visible",
        "insufficient_localization_evidence",
    ] | None
    organs: list[AnatomyLocalizationOrganResponse]


class AnatomyLocalizationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["xray-anatomy-localization.v1"]
    label_contract_version: Literal["xray-anatomy-labels.v1"]
    species: Literal["cat", "dog"]
    result_status: Literal["complete", "partial", "unavailable"]
    images: list[AnatomyLocalizationImageResponse] = Field(
        min_length=2,
        max_length=5,
    )


class AnatomyLocalizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    study_id: str
    study_revision_id: str
    stage_checkpoint_id: str
    source_call_id: str
    output_sha256: str
    result: AnatomyLocalizationResultResponse


__all__ = [
    "AnatomyLocalizationImageResponse",
    "AnatomyLocalizationLegendLabelResponse",
    "AnatomyLocalizationLegendResponse",
    "AnatomyLocalizationLegendSystemResponse",
    "AnatomyLocalizationOrganResponse",
    "AnatomyLocalizationPrepareViewRequest",
    "AnatomyLocalizationPrepareViewResponse",
    "AnatomyLocalizationResponse",
    "AnatomyLocalizationResultResponse",
    "AnatomyLocalizationViewImageResponse",
]
