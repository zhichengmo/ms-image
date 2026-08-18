from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, field_validator

from .image_contract import normalize_source_mime_type

from .run import XRayRunResponse


class XRaySessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    case_request_id: str | None = Field(default=None, max_length=128)
    module_key: str = Field(default="xray", min_length=1, max_length=64)
    metadata: dict[str, Any] | None = None


class XRaySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    tenant_id: str
    subject_id: str
    case_request_id: str | None = None
    module_key: str
    session_status: str
    created_at: datetime | None = None
    closed_at: datetime | None = None
    event_count: int = 0


class XRaySessionCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)


class XRayStudyImageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_index: NonNegativeInt
    source_image_ref: str = Field(min_length=1, max_length=512)
    mime_type: str | None = Field(default=None, max_length=128)
    projection: str | None = Field(default=None, max_length=64)
    body_part: str | None = Field(default=None, max_length=64)
    safe_metadata: dict[str, Any] | None = None

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str | None) -> str | None:
        return normalize_source_mime_type(value)


class XRayStudyPreparationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=64)
    study_id: str = Field(min_length=1, max_length=128)
    study_revision_id: str | None = Field(default=None, max_length=128)
    images: list[XRayStudyImageCreate] = Field(min_length=1, max_length=256)
    species: str | None = Field(default=None, max_length=32)
    body_scope: str | None = Field(default=None, max_length=64)
    safe_metadata: dict[str, Any] | None = None


class XRayStudySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    study_id: str
    study_revision_id: str
    session_id: str
    study_status: str
    expected_image_count: int
    expected_manifest_sha256: str
    coverage_status: str
    identity_confidence: str
    body_scope: str | None = None
    species: str | None = None
    frozen_at: datetime | None = None


class XRayImageAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: str
    study_revision_id: str
    source_index: int
    asset_role: str
    asset_status: str
    content_sha256: str | None = None
    mime_type: str | None = None
    byte_size: int | None = None
    pixel_width: int | None = None
    pixel_height: int | None = None
    projection: str | None = None
    body_part: str | None = None
    object_available: bool


class XRaySessionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    session_id: str
    event_type: str
    payload_hash: str
    trace_namespace: str
    created_at: datetime | None = None
    created_by: str


class XRayStudyDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    study: XRayStudySnapshotResponse
    assets: list[XRayImageAssetResponse]


class XRayStudyPreparationResponse(XRayStudyDetailResponse):
    run: XRayRunResponse | None = None
