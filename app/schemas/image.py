from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.imaging.object_store import MAX_IMAGE_BYTES
from app.schemas.imaging_common import normalize_required_text, normalize_utc_datetime


IMAGE_ROLES = frozenset(
    {"original", "display", "thumbnail", "normalized", "derived", "segmentation"}
)
IMAGE_KINDS = frozenset({"instance", "photo", "cine", "video", "wsi", "volume", "other"})
FILE_FORMATS = frozenset({"dicom", "jpeg", "png", "mp4", "nifti", "tiff", "svs", "other"})
UPLOAD_MODES = frozenset({"direct_put", "multipart", "internal_import"})
QUALIFIED_UPLOAD_FORMATS = frozenset({"dicom", "jpeg", "png"})
QUALIFIED_CONTENT_TYPES = {
    "dicom": "application/dicom",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


class ImageCreate(BaseModel):
    """Internal creation contract; object_key must come from ObjectStorageGateway."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1, max_length=64)
    source_image_id: str | None = Field(default=None, max_length=128)
    logical_image_key: str = Field(min_length=1, max_length=128)
    source_manifest: list[dict[str, Any]] | None = None
    sequence_no: int = Field(ge=1)
    image_role: str = Field(min_length=1, max_length=32)
    image_kind: str = Field(min_length=1, max_length=32)
    metadata_schema_version: str = Field(min_length=1, max_length=64)
    storage_profile: str = Field(min_length=1, max_length=40)
    object_key: str = Field(min_length=1, max_length=512)
    file_format: str = Field(min_length=1, max_length=32)
    upload_mode: str = Field(min_length=1, max_length=32)
    upload_session_ref: str | None = Field(default=None, max_length=256)
    expected_part_count: int | None = Field(default=None, ge=1)
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_size_bytes: int | None = Field(default=None, ge=1)
    declared_content_type: str | None = Field(default=None, max_length=128)
    technical_metadata: dict[str, Any] | None = None
    upload_expires_at: datetime | None = None

    @field_validator(
        "series_id",
        "logical_image_key",
        "metadata_schema_version",
        "storage_profile",
        "object_key",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("image_role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in IMAGE_ROLES:
            raise ValueError("image_role_invalid")
        return normalized

    @field_validator("image_kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in IMAGE_KINDS:
            raise ValueError("image_kind_invalid")
        return normalized

    @field_validator("file_format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in FILE_FORMATS:
            raise ValueError("image_format_invalid")
        return normalized

    @field_validator("upload_mode")
    @classmethod
    def validate_upload_mode(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in UPLOAD_MODES:
            raise ValueError("image_upload_mode_invalid")
        return normalized

    @field_validator(
        "source_image_id",
        "upload_session_ref",
        "declared_content_type",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("upload_expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def validate_upload_contract(self):
        if self.upload_mode == "multipart":
            if not self.upload_session_ref or self.expected_part_count is None:
                raise ValueError("multipart_upload_contract_incomplete")
        elif self.upload_session_ref is not None or self.expected_part_count is not None:
            raise ValueError("non_multipart_upload_has_part_contract")
        if self.image_role == "original" and self.source_manifest:
            raise ValueError("original_image_source_manifest_forbidden")
        if self.image_role != "original" and not self.source_manifest:
            raise ValueError("derived_image_source_manifest_required")
        return self


class ImageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=0)


class ImagePrepareUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1, max_length=64)
    source_image_id: str | None = Field(default=None, max_length=128)
    logical_image_key: str = Field(min_length=1, max_length=128)
    source_manifest: list[dict[str, Any]] | None = None
    sequence_no: int = Field(ge=1)
    image_role: str = Field(min_length=1, max_length=32)
    image_kind: str = Field(min_length=1, max_length=32)
    metadata_schema_version: str = Field(min_length=1, max_length=64)
    file_format: str = Field(min_length=1, max_length=32)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_size_bytes: int = Field(ge=1, le=MAX_IMAGE_BYTES)
    declared_content_type: str = Field(min_length=1, max_length=128)
    technical_metadata: dict[str, Any] | None = None

    @field_validator("series_id", "logical_image_key", "metadata_schema_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("source_image_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("image_role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in IMAGE_ROLES:
            raise ValueError("image_role_invalid")
        return normalized

    @field_validator("image_kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in IMAGE_KINDS:
            raise ValueError("image_kind_invalid")
        return normalized

    @field_validator("file_format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in QUALIFIED_UPLOAD_FORMATS:
            raise ValueError("image_format_not_qualified")
        return normalized

    @field_validator("declared_content_type")
    @classmethod
    def normalize_content_type(cls, value: str) -> str:
        normalized = normalize_required_text(value).casefold()
        return "image/jpeg" if normalized == "image/jpg" else normalized

    @model_validator(mode="after")
    def validate_prepare_contract(self):
        if QUALIFIED_CONTENT_TYPES[self.file_format] != self.declared_content_type:
            raise ValueError("image_format_content_type_mismatch")
        if self.image_role == "original" and self.source_manifest:
            raise ValueError("original_image_source_manifest_forbidden")
        if self.image_role != "original" and not self.source_manifest:
            raise ValueError("derived_image_source_manifest_required")
        return self


class ImagePrepareMultipartRequest(ImagePrepareUploadRequest):
    expected_part_count: int = Field(ge=1, le=10000)


class ImageUploadTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: "ImageResponse"
    generation: int = Field(ge=1)
    upload_mode: str
    required_headers: dict[str, str]
    expires_at: datetime
    signed_url: str = Field(repr=False)


class ImageMultipartUploadTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: "ImageResponse"
    generation: int = Field(ge=1)
    upload_mode: str
    required_headers: dict[str, str]
    expires_at: datetime
    upload_session_ref: str = Field(min_length=1, max_length=256, repr=False)


class ImagePreparePartsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    generation: int = Field(ge=1)
    part_numbers: list[int] = Field(min_length=1, max_length=1000)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("part_numbers")
    @classmethod
    def validate_parts(cls, value: list[int]) -> list[int]:
        if any(item < 1 or item > 10000 for item in value):
            raise ValueError("multipart_part_number_invalid")
        if len(set(value)) != len(value):
            raise ValueError("multipart_part_number_duplicate")
        return sorted(value)


class ImageSignedPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(ge=1)
    signed_url: str = Field(repr=False)


class ImageMultipartPartsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    generation: int = Field(ge=1)
    parts: list[ImageSignedPart]


class ImageMultipartPartReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(ge=1, le=10000)
    etag: str = Field(min_length=1, max_length=256)
    size_bytes: int | None = Field(default=None, ge=1)

    @field_validator("etag")
    @classmethod
    def normalize_etag(cls, value: str) -> str:
        return normalize_required_text(value)


class ImageCompleteUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    generation: int = Field(ge=1)
    trace_id: str = Field(min_length=1, max_length=128)
    parts: list[ImageMultipartPartReceipt] | None = Field(
        default=None, max_length=10000
    )

    @field_validator("id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("parts")
    @classmethod
    def validate_part_receipts(
        cls, value: list[ImageMultipartPartReceipt] | None
    ) -> list[ImageMultipartPartReceipt] | None:
        if value is None:
            return None
        numbers = [item.part_number for item in value]
        if len(set(numbers)) != len(numbers):
            raise ValueError("multipart_part_number_duplicate")
        return sorted(value, key=lambda item: item.part_number)


class ImageReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_image_id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    source_image_id: str | None = Field(default=None, max_length=128)
    metadata_schema_version: str = Field(min_length=1, max_length=64)
    file_format: str = Field(min_length=1, max_length=32)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_size_bytes: int = Field(ge=1, le=MAX_IMAGE_BYTES)
    declared_content_type: str = Field(min_length=1, max_length=128)
    technical_metadata: dict[str, Any] | None = None

    @field_validator("old_image_id", "metadata_schema_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("source_image_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("file_format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in QUALIFIED_UPLOAD_FORMATS:
            raise ValueError("image_format_not_qualified")
        return normalized

    @field_validator("declared_content_type")
    @classmethod
    def normalize_content_type(cls, value: str) -> str:
        normalized = normalize_required_text(value).casefold()
        return "image/jpeg" if normalized == "image/jpg" else normalized

    @model_validator(mode="after")
    def validate_replace_contract(self):
        if QUALIFIED_CONTENT_TYPES[self.file_format] != self.declared_content_type:
            raise ValueError("image_format_content_type_mismatch")
        return self


class ImageAbortCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    generation: int | None = Field(default=None, ge=1)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    series_id: str
    source_image_id: str | None = None
    logical_image_key: str
    image_version_no: int
    supersedes_image_id: str | None = None
    source_manifest_json: list[dict[str, Any]] | dict[str, Any] | None = None
    sequence_no: int
    image_role: str
    image_kind: str
    metadata_schema_version: str
    storage_profile: str
    object_key: str
    object_version_id: str | None = None
    file_format: str
    upload_mode: str
    expected_part_count: int | None = None
    expected_sha256: str | None = None
    expected_size_bytes: int | None = None
    declared_content_type: str | None = None
    content_type: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    kms_key_version: str | None = None
    sop_instance_uid: str | None = None
    sop_class_uid: str | None = None
    instance_no: int | None = None
    projection: str | None = None
    technical_metadata_json: dict[str, Any] | None = None
    status: str
    state_version: int
    validation_lease_generation: int
    validation_attempt_count: int
    next_validation_at: datetime | None = None
    error_code: str | None = None
    upload_expires_at: datetime | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "FILE_FORMATS",
    "IMAGE_KINDS",
    "IMAGE_ROLES",
    "MAX_IMAGE_BYTES",
    "QUALIFIED_UPLOAD_FORMATS",
    "UPLOAD_MODES",
    "ImageAbortCommand",
    "ImageCompleteUploadRequest",
    "ImageCreate",
    "ImageMultipartPartReceipt",
    "ImageMultipartPartsResponse",
    "ImageMultipartUploadTicket",
    "ImagePrepareMultipartRequest",
    "ImagePreparePartsRequest",
    "ImagePrepareUploadRequest",
    "ImageResponse",
    "ImageReplaceRequest",
    "ImageSignedPart",
    "ImageUploadTicket",
    "ImageUpdate",
]
