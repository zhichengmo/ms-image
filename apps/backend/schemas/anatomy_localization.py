"""Owner-safe Runtime responses for Anatomy Localization v1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    "AnatomyLocalizationOrganResponse",
    "AnatomyLocalizationResponse",
    "AnatomyLocalizationResultResponse",
]
