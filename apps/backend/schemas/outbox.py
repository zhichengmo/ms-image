from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.imaging_common import normalize_required_text


class ValidateImageMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=1)
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("image_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


class ExecuteStageMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    stage_checkpoint_id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("task_id", "stage_checkpoint_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


__all__ = ["ExecuteStageMessage", "ValidateImageMessage"]
