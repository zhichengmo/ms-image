from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.imaging_common import normalize_required_text


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    revision_no: int
    source_stage_checkpoint_id: str
    source_call_id: str | None = None
    medical_status: str
    content_json: dict[str, Any]
    content_sha256: str
    status: str
    render_manifest_json: dict[str, Any] | None = None
    published_at: datetime | None = None
    voided_at: datetime | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class ReportStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


__all__ = ["ReportResponse", "ReportStateRequest"]
