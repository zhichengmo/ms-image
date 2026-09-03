from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.backend.schemas.imaging_common import normalize_required_text


class PetInfoQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species: str = Field(min_length=1, max_length=32)
    query_key: str | None = Field(default=None, max_length=128)
    group_by_first_letter: bool = True

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str) -> str:
        normalized = normalize_required_text(value).lower()
        if normalized not in {"cat", "dog"}:
            raise ValueError("pet_info_species_invalid")
        return normalized

    @field_validator("query_key")
    @classmethod
    def normalize_query_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PetInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    species: str
    full_name: str
    name: str
    english_name: str | None = None
    alias: str | None = None
    origin_place: str | None = None
    figure: str | None = None
    reference_weight_kg: Decimal | None = None
    fur_length: str | None = None
    features: str | None = None
    description: str | None = None
    image_keys_json: list[str] | None = None
    source_url: str | None = None
    first_letter: str
    status: str
    created_at: datetime
    updated_at: datetime


class PetInfoGroupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_letter: str = Field(min_length=1, max_length=1)
    items: list[PetInfoResponse]


class PetInfoCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species: str
    grouped: bool
    total: int = Field(ge=0)
    groups: list[PetInfoGroupResponse] = Field(default_factory=list)
    items: list[PetInfoResponse] = Field(default_factory=list)


__all__ = [
    "PetInfoCatalogResponse",
    "PetInfoGroupResponse",
    "PetInfoQuery",
    "PetInfoResponse",
]
