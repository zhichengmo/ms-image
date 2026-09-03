from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.backend.schemas.imaging_common import (
    normalize_required_text,
    normalize_utc_datetime,
)


PET_SPECIES = frozenset({"cat", "dog", "other"})
PET_SEXES = frozenset({"male", "female", "unknown"})
PET_NEUTER_STATUSES = frozenset({"intact", "neutered", "unknown"})
PET_VACCINATION_STATUSES = frozenset(
    {"vaccinated", "unvaccinated", "partial", "unknown"}
)
PET_PROFILE_STATUSES = frozenset({"active", "archived", "deceased"})
PET_PROFILE_MUTABLE_FIELDS = frozenset(
    {
        "name",
        "species",
        "breed_name",
        "sex",
        "neuter_status",
        "vaccination_status",
        "birthday",
        "avatar_object_key",
        "weight_kg",
        "weight_measured_at",
        "last_vaccinated_at",
        "last_examined_at",
        "diet_notes",
        "disease_history",
        "allergy_history",
        "family_history",
        "care_notes",
        "health_notes",
        "medical_history",
    }
)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_choice(value: str, allowed: frozenset[str], error: str) -> str:
    normalized = normalize_required_text(value).lower()
    if normalized not in allowed:
        raise ValueError(error)
    return normalized


def _normalize_object_key(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if "://" in normalized or "?" in normalized or "#" in normalized:
        raise ValueError("pet_avatar_object_key_invalid")
    normalized = normalized.lstrip("/")
    if not normalized:
        raise ValueError("pet_avatar_object_key_invalid")
    return normalized


class PetProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    source_system: str | None = Field(default=None, max_length=64)
    source_pet_id: str | None = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=64)
    species: str = Field(min_length=1, max_length=32)
    breed_name: str | None = Field(default=None, max_length=128)
    sex: str = Field(default="unknown", min_length=1, max_length=32)
    neuter_status: str = Field(default="unknown", min_length=1, max_length=32)
    vaccination_status: str = Field(default="unknown", min_length=1, max_length=32)
    birthday: date | None = None
    avatar_object_key: str | None = Field(default=None, max_length=512)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=99999)
    weight_measured_at: datetime | None = None
    last_vaccinated_at: datetime | None = None
    last_examined_at: datetime | None = None
    diet_notes: str | None = None
    disease_history: str | None = None
    allergy_history: str | None = None
    family_history: str | None = None
    care_notes: str | None = None
    health_notes: str | None = None
    medical_history: str | None = None

    @field_validator("request_id", "name")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator(
        "source_system",
        "source_pet_id",
        "breed_name",
        "diet_notes",
        "disease_history",
        "allergy_history",
        "family_history",
        "care_notes",
        "health_notes",
        "medical_history",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str) -> str:
        return _validate_choice(value, PET_SPECIES, "pet_species_invalid")

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, value: str) -> str:
        return _validate_choice(value, PET_SEXES, "pet_sex_invalid")

    @field_validator("neuter_status")
    @classmethod
    def validate_neuter_status(cls, value: str) -> str:
        return _validate_choice(value, PET_NEUTER_STATUSES, "pet_neuter_status_invalid")

    @field_validator("vaccination_status")
    @classmethod
    def validate_vaccination_status(cls, value: str) -> str:
        return _validate_choice(
            value, PET_VACCINATION_STATUSES, "pet_vaccination_status_invalid"
        )

    @field_validator("avatar_object_key")
    @classmethod
    def normalize_avatar_object_key(cls, value: str | None) -> str | None:
        return _normalize_object_key(value)

    @field_validator("weight_measured_at", "last_vaccinated_at", "last_examined_at")
    @classmethod
    def normalize_event_time(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def validate_source_identity(self) -> "PetProfileCreate":
        if (self.source_system is None) != (self.source_pet_id is None):
            raise ValueError("pet_source_identity_incomplete")
        return self


class PetProfileUpdateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    species: str | None = Field(default=None, min_length=1, max_length=32)
    breed_name: str | None = Field(default=None, max_length=128)
    sex: str | None = Field(default=None, min_length=1, max_length=32)
    neuter_status: str | None = Field(default=None, min_length=1, max_length=32)
    vaccination_status: str | None = Field(default=None, min_length=1, max_length=32)
    birthday: date | None = None
    avatar_object_key: str | None = Field(default=None, max_length=512)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=99999)
    weight_measured_at: datetime | None = None
    last_vaccinated_at: datetime | None = None
    last_examined_at: datetime | None = None
    diet_notes: str | None = None
    disease_history: str | None = None
    allergy_history: str | None = None
    family_history: str | None = None
    care_notes: str | None = None
    health_notes: str | None = None
    medical_history: str | None = None

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else None

    @field_validator(
        "breed_name",
        "diet_notes",
        "disease_history",
        "allergy_history",
        "family_history",
        "care_notes",
        "health_notes",
        "medical_history",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str | None) -> str | None:
        return (
            _validate_choice(value, PET_SPECIES, "pet_species_invalid")
            if value is not None
            else None
        )

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, value: str | None) -> str | None:
        return (
            _validate_choice(value, PET_SEXES, "pet_sex_invalid")
            if value is not None
            else None
        )

    @field_validator("neuter_status")
    @classmethod
    def validate_neuter_status(cls, value: str | None) -> str | None:
        return (
            _validate_choice(value, PET_NEUTER_STATUSES, "pet_neuter_status_invalid")
            if value is not None
            else None
        )

    @field_validator("vaccination_status")
    @classmethod
    def validate_vaccination_status(cls, value: str | None) -> str | None:
        return (
            _validate_choice(
                value, PET_VACCINATION_STATUSES, "pet_vaccination_status_invalid"
            )
            if value is not None
            else None
        )

    @field_validator("avatar_object_key")
    @classmethod
    def normalize_avatar_object_key(cls, value: str | None) -> str | None:
        return _normalize_object_key(value)

    @field_validator("weight_measured_at", "last_vaccinated_at", "last_examined_at")
    @classmethod
    def normalize_event_time(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def require_update_field(self) -> "PetProfileUpdateCommand":
        selected = self.model_fields_set & PET_PROFILE_MUTABLE_FIELDS
        if not selected:
            raise ValueError("pet_profile_update_empty")
        required_fields = {
            "name",
            "species",
            "sex",
            "neuter_status",
            "vaccination_status",
        }
        if any(getattr(self, field) is None for field in selected & required_fields):
            raise ValueError("pet_profile_required_field_null")
        return self


class PetProfileArchiveCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    archive_reason: str = Field(min_length=1, max_length=500)

    @field_validator("id", "archive_reason")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        return normalize_required_text(value)


class PetProfileRestoreCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_required_text(value)


class PetProfilePageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default="active", min_length=1, max_length=32)
    species: str | None = Field(default=None, min_length=1, max_length=32)
    query_key: str | None = Field(default=None, max_length=128)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return (
            _validate_choice(value, PET_PROFILE_STATUSES, "pet_profile_status_invalid")
            if value is not None
            else None
        )

    @field_validator("species")
    @classmethod
    def validate_species(cls, value: str | None) -> str | None:
        return (
            _validate_choice(value, PET_SPECIES, "pet_species_invalid")
            if value is not None
            else None
        )

    @field_validator("query_key")
    @classmethod
    def normalize_query_key(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class PetProfileHistoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pet_profile_id: str = Field(min_length=1, max_length=64)
    operation_type: str | None = Field(default=None, min_length=1, max_length=32)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    @field_validator("pet_profile_id")
    @classmethod
    def normalize_profile_id(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("operation_type")
    @classmethod
    def validate_operation_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_required_text(value).lower()
        if normalized not in {"create", "update", "archive", "restore"}:
            raise ValueError("pet_history_operation_invalid")
        return normalized


class PetProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    request_id: str
    source_system: str | None = None
    source_pet_id: str | None = None
    name: str
    species: str
    breed_name: str | None = None
    sex: str
    neuter_status: str
    vaccination_status: str
    birthday: date | None = None
    avatar_object_key: str | None = None
    weight_kg: Decimal | None = None
    weight_measured_at: datetime | None = None
    last_vaccinated_at: datetime | None = None
    last_examined_at: datetime | None = None
    diet_notes: str | None = None
    disease_history: str | None = None
    allergy_history: str | None = None
    family_history: str | None = None
    care_notes: str | None = None
    health_notes: str | None = None
    medical_history: str | None = None
    status: str
    state_version: int
    archived_at: datetime | None = None
    archived_by_id: str | None = None
    archive_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class PetProfilePageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[PetProfileResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)


class PetProfileHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pet_profile_id: str
    data_type: str
    field_name: str
    old_value_json: Any | None = None
    new_value_json: Any | None = None
    operation_type: str
    operator_id: str
    snapshot_json: dict[str, Any] | None = None
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class PetProfileHistoryPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[PetProfileHistoryResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)


__all__ = [
    "PET_NEUTER_STATUSES",
    "PET_PROFILE_MUTABLE_FIELDS",
    "PET_PROFILE_STATUSES",
    "PET_SEXES",
    "PET_SPECIES",
    "PET_VACCINATION_STATUSES",
    "PetProfileArchiveCommand",
    "PetProfileCreate",
    "PetProfileHistoryPageResult",
    "PetProfileHistoryQuery",
    "PetProfileHistoryResponse",
    "PetProfilePageQuery",
    "PetProfilePageResult",
    "PetProfileResponse",
    "PetProfileRestoreCommand",
    "PetProfileUpdateCommand",
]
