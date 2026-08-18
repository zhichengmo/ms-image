from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.imaging_common import normalize_required_text, normalize_utc_datetime


MODALITY_TYPES = frozenset(
    {
        "xray",
        "ct",
        "mri",
        "ultrasound",
        "endoscopy",
        "pathology",
        "clinical_photo",
        "dental_xray",
        "other",
    }
)
IDENTITY_STATUSES = frozenset({"unknown", "confirmed", "conflict"})


class StudyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    source_study_id: str | None = Field(default=None, max_length=128)
    modality_type: str = Field(min_length=1, max_length=32)
    dicom_study_uid: str | None = Field(default=None, max_length=128)
    body_part: str | None = Field(default=None, max_length=128)
    metadata_schema_version: str = Field(min_length=1, max_length=64)
    expected_image_count: int | None = Field(default=None, ge=0)
    expected_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    completeness_attested_by: str | None = Field(default=None, max_length=128)
    identity_status: str = "unknown"
    technical_metadata: dict[str, Any] | None = None
    acquired_at: datetime | None = None

    @field_validator("session_id", "metadata_schema_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("modality_type")
    @classmethod
    def validate_modality(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in MODALITY_TYPES:
            raise ValueError("study_modality_invalid")
        return normalized

    @field_validator("identity_status")
    @classmethod
    def validate_identity_status(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in IDENTITY_STATUSES:
            raise ValueError("study_identity_status_invalid")
        return normalized

    @field_validator(
        "source_study_id",
        "dicom_study_uid",
        "body_part",
        "completeness_attested_by",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("acquired_at")
    @classmethod
    def normalize_acquired_at(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None


class StudyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=0)
    current_revision_id: str = Field(min_length=1, max_length=64)


class SeriesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str = Field(min_length=1, max_length=64)
    series_key: str = Field(min_length=1, max_length=128)
    dicom_series_uid: str | None = Field(default=None, max_length=128)
    series_no: int | None = Field(default=None, ge=1)
    metadata_schema_version: str = Field(min_length=1, max_length=64)
    expected_image_count: int | None = Field(default=None, ge=0)
    technical_metadata: dict[str, Any] | None = None
    acquired_at: datetime | None = None

    @field_validator("study_id", "series_key", "metadata_schema_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("dicom_series_uid")
    @classmethod
    def normalize_dicom_uid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("acquired_at")
    @classmethod
    def normalize_acquired_at(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None


class SeriesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=0)


class SeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    series_key: str
    dicom_series_uid: str | None = None
    series_no: int | None = None
    metadata_schema_version: str
    expected_image_count: int | None = None
    actual_image_count: int
    manifest_sha256: str | None = None
    status: str
    state_version: int
    technical_metadata_json: dict[str, Any] | None = None
    acquired_at: datetime | None = None
    ready_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    source_study_id: str
    modality_type: str
    dicom_study_uid: str | None = None
    body_part: str | None = None
    metadata_schema_version: str
    revision_no: int
    revision_id: str
    revision_reason: str | None = None
    revision_changed_at: datetime
    expected_image_count: int | None = None
    expected_manifest_sha256: str | None = None
    resolved_manifest_sha256: str | None = None
    completeness_status: str
    completeness_attested_by: str | None = None
    identity_status: str
    status: str
    state_version: int
    technical_metadata_json: dict[str, Any] | None = None
    acquired_at: datetime | None = None
    ready_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudyDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study: StudyResponse
    series: list[SeriesResponse]


__all__ = [
    "IDENTITY_STATUSES",
    "MODALITY_TYPES",
    "SeriesCreate",
    "SeriesResponse",
    "SeriesUpdate",
    "StudyCreate",
    "StudyDetailResponse",
    "StudyResponse",
    "StudyUpdate",
]
