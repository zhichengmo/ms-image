from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.imaging_common import normalize_required_text


class ValidateImageMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=1)
    trace_id: str = Field(min_length=1, max_length=128)

    @field_validator("image_id", "trace_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return normalize_required_text(value)


__all__ = ["ValidateImageMessage"]
